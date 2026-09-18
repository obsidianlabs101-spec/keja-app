from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, case, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.message import Message
from app.models.user_follow import UserFollow
from app.schemas.message import (
    MessageSendRequest,
    MessageResponse,
    ThreadSummary,
    UnreadCountResponse,
)
from app.services.push_service import send_web_push

router = APIRouter(prefix="/messages", tags=["Messages"])


def _norm_username(u: str) -> str:
    # Usernames are stored with a leading "@" (see app.api.v1.users._norm_username);
    # callers sometimes pass it without one, so normalize before every lookup.
    u = (u or "").strip()
    return u if u.startswith("@") else f"@{u}"


def _is_squad(db: Session, user_a_id, user_b_id) -> bool:
    """
    "Squad" == mutual accepted follow (matches the frontend's definition:
    following ∩ followers). One-on-one messaging is squad-only, so this
    gate has to live here too — not just hidden in the UI — otherwise
    anyone could still POST straight to /messages/send.
    """
    a_follows_b = db.query(UserFollow).filter(
        UserFollow.follower_id == user_a_id,
        UserFollow.followee_id == user_b_id,
        UserFollow.status == "accepted",
    ).first()
    if not a_follows_b:
        return False
    b_follows_a = db.query(UserFollow).filter(
        UserFollow.follower_id == user_b_id,
        UserFollow.followee_id == user_a_id,
        UserFollow.status == "accepted",
    ).first()
    return bool(b_follows_a)


@router.post("/send", response_model=MessageResponse)
def send_message(
    data: MessageSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Find receiver
    receiver = db.query(User).filter(func.lower(User.username) == _norm_username(data.to_username).lower()).first()
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    if receiver.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send message to yourself")
    if not _is_squad(db, current_user.id, receiver.id):
        raise HTTPException(
            status_code=403,
            detail="You can only message squad members — you both need to follow each other first.",
        )

    context = (data.context or "user").strip().lower()
    if context not in ("user", "host"):
        context = "user"

    msg = Message(
        sender_id=current_user.id,
        receiver_id=receiver.id,
        text=data.text,
        created_at=datetime.now(timezone.utc),
        read=False,
        context=context,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Real phone/OS notification-tray alert. The banner image is the
    # SENDER's own avatar, not the BASH logo — for a DM, seeing who it's
    # from matters more than branding, and the small icon/badge in the
    # corner (see sw.js) already carries the BASH mark regardless. tag
    # groups repeated messages from the same sender into one notification
    # instead of flooding the tray with a separate entry per message.
    send_web_push(
        db, receiver,
        title=f"💬 {current_user.username}",
        body=msg.text[:140],
        data={
            "type": "squad_message",
            "sender_username": current_user.username,
            "sender_id": str(current_user.id),
        },
        image=current_user.profile_picture,
        tag=f"squad-msg-{current_user.id}",
    )

    return MessageResponse(
        id=str(msg.id),
        sender_username=current_user.username,
        receiver_username=receiver.username,
        text=msg.text,
        created_at=msg.created_at,
        read=msg.read,
        context=msg.context,
    )


def _clean_context(context: str) -> str:
    context = (context or "user").strip().lower()
    return context if context in ("user", "host") else "user"


@router.get("/thread/{username}", response_model=List[MessageResponse])
def get_thread(
    username: str,
    context: str = "user",
    limit: int = Query(50, ge=1, le=200),
    before: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = _clean_context(context)
    other = db.query(User).filter(func.lower(User.username) == _norm_username(username).lower()).first()
    if not other:
        raise HTTPException(status_code=404, detail="User not found")

    base_filter = (
        (
            ((Message.sender_id == current_user.id) & (Message.receiver_id == other.id))
            | ((Message.sender_id == other.id) & (Message.receiver_id == current_user.id))
        )
        & (Message.context == context)
    )

    query = db.query(Message).filter(base_filter)
    if before:
        # Cursor pagination for "load older messages" — pass the oldest
        # created_at already on screen to page further back.
        try:
            before_dt = datetime.fromisoformat(before)
            query = query.filter(Message.created_at < before_dt)
        except ValueError:
            pass

    # A live chat window only ever needs its most recent slice, not the
    # entire history re-fetched on every 3s poll tick (see profile.js
    # CHAT_POLL_MS) — that payload only grows with a thread's age, not
    # with how many people are using the app, so it's pure waste at scale.
    # Fetch newest-first with a LIMIT (fast, index-backed), then flip back
    # to chronological order for display.
    messages = query.order_by(Message.created_at.desc()).limit(limit).all()
    messages.reverse()

    # Mark incoming messages as read with a single bulk UPDATE instead of
    # looping over every row in Python and dirtying it — this used to touch
    # every message ever exchanged with `other` on every single poll tick;
    # now it's one indexed UPDATE (see ix_messages_receiver_unread) that
    # only touches rows that are actually still unread.
    db.query(Message).filter(
        Message.sender_id == other.id,
        Message.receiver_id == current_user.id,
        Message.context == context,
        Message.read.is_(False),
    ).update({"read": True}, synchronize_session=False)
    db.commit()

    for m in messages:
        if m.sender_id == other.id:
            m.read = True  # reflect the update above in this response

    return [
        MessageResponse(
            id=str(m.id),
            sender_username=m.sender.username,
            receiver_username=m.receiver.username,
            text=m.text,
            created_at=m.created_at,
            read=m.read,
            context=m.context,
        )
        for m in messages
    ]


@router.get("/threads", response_model=List[ThreadSummary])
def get_threads(
    context: str = "user",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = _clean_context(context)
    uid = current_user.id
    # Scoped to this inbox only — a host's dashboard inbox ("host") never
    # mixes with their personal profile inbox ("user"), even though it's
    # the same underlying account.

    # The old version pulled EVERY message the user has ever sent or
    # received just to find the latest one per conversation partner, then
    # ran one extra User lookup per partner in a Python loop (N+1). Both
    # of those get slower forever as history piles up, regardless of how
    # many people are actually using BASH concurrently. This does it in
    # 3 fixed-size queries instead:
    #   1) one windowed query that returns only the latest message per
    #      partner (row_number() over partition by other_user)
    #   2) one grouped query for unread counts per partner
    #   3) one batched User lookup for all partners at once
    other_id_expr = case(
        (Message.sender_id == uid, Message.receiver_id),
        else_=Message.sender_id,
    ).label("other_id")

    ranked = (
        db.query(
            other_id_expr,
            Message.text.label("text"),
            Message.created_at.label("created_at"),
            func.row_number()
            .over(partition_by=other_id_expr, order_by=Message.created_at.desc())
            .label("rn"),
        )
        .filter(
            or_(Message.sender_id == uid, Message.receiver_id == uid),
            Message.context == context,
        )
        .subquery()
    )
    latest_rows = db.query(ranked).filter(ranked.c.rn == 1).all()
    if not latest_rows:
        return []

    unread_rows = (
        db.query(Message.sender_id, func.count(Message.id))
        .filter(
            Message.receiver_id == uid,
            Message.read.is_(False),
            Message.context == context,
        )
        .group_by(Message.sender_id)
        .all()
    )
    unread_map = {sender_id: count for sender_id, count in unread_rows}

    other_ids = [row.other_id for row in latest_rows]
    users = db.query(User).filter(User.id.in_(other_ids)).all()
    user_map = {u.id: u for u in users}

    result = []
    for row in latest_rows:
        other_user = user_map.get(row.other_id)
        if not other_user:
            continue  # partner account no longer exists — skip, don't 500
        result.append(
            ThreadSummary(
                username=other_user.username,
                last_message=row.text,
                last_time=row.created_at,
                unread=unread_map.get(row.other_id, 0),
                context=context,
            )
        )

    result.sort(key=lambda x: x.last_time, reverse=True)
    return result


@router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    context: str = "user",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    context = _clean_context(context)
    count = db.query(func.count(Message.id)).filter(
        Message.receiver_id == current_user.id,
        Message.read == False,
        Message.context == context,
    ).scalar() or 0
    return UnreadCountResponse(unread=count)