from sqlalchemy.orm import Session

from app.models.admin import Admin
from app.schemas.admin import AdminRegister
from app.core.security import hash_password
from app.core.security import verify_password
from app.models.admin_activity_log import AdminActivityLog


def log_admin_activity(db: Session, admin_id, action: str, detail: str = None, amount: float = None):
    """Records one row on the admin Financials page's 'Cuto' activity
    trail. Best-effort — a logging failure should never break the action
    it's attached to, so callers can fire-and-forget this."""
    try:
        db.add(AdminActivityLog(admin_id=admin_id, action=action, detail=detail, amount=amount))
    except Exception as e:
        print(f"Admin activity log skipped: {e}")


def get_admin_by_email(
    db: Session,
    email: str
):

    return (
        db.query(Admin)
        .filter(Admin.email == email)
        .first()
    )


def get_admin_by_id(
    db: Session,
    admin_id: str
):

    return (
        db.query(Admin)
        .filter(Admin.id == admin_id)
        .first()
    )


def create_admin(
    db: Session,
    data: AdminRegister
):

    admin = Admin(
        username=data.username,
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password)
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)

    return admin


def authenticate_admin(
    db: Session,
    email: str,
    password: str
):

    admin = get_admin_by_email(db, email)
    if not admin:
        return None

    if not verify_password(password, admin.password_hash):
        return None

    return admin