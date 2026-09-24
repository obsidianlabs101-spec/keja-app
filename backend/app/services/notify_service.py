# app/services/notify_service.py
from app.models.notification import Notification


def notify(db, user_id, type_: str, title: str, body: str = None, data: dict = None, commit: bool = True):
    """Adds an item to the user's Alerts (the bell on Home). Uses the
    existing notifications table with context="user"."""
    n = Notification(user_id=user_id, type=type_, title=title, body=body, data=data or {}, context="user")
    db.add(n)
    if commit:
        db.commit()
    return n


def notify_contact_ready(db, unlock, prop=None, commit: bool = True):
    """Sends the landlord's number to the renter's Alerts for a property."""
    prop = prop or unlock.property
    landlord = prop.landlord if prop else None
    phone = (landlord.phone if landlord else None) or ""
    name = (landlord.full_name if landlord else None) or "the landlord"
    title = f"Contact ready: {prop.title}" if prop else "Landlord contact ready"
    body = f"{name}: {phone}" if phone else f"{name} hasn't added a phone number yet — we'll follow up."
    return notify(
        db, unlock.user_id, "contact_unlocked", title, body,
        {"property_id": str(unlock.property_id), "phone": phone, "landlord_name": name},
        commit=commit,
    )
