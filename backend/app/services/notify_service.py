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


def notify_property_booked(db, prop, commit: bool = True):
    """Tells everyone who has this property in their Interested list that
    it's been booked (either by the landlord or an admin), so they don't
    waste a trip or a payment on it."""
    from app.models.interested_property import InterestedProperty
    rows = db.query(InterestedProperty).filter(InterestedProperty.property_id == prop.id).all()
    for row in rows:
        notify(
            db, row.user_id, "property_booked",
            f"No longer available: {prop.title}",
            "This property has just been booked by someone else. We'll keep finding you others like it.",
            {"property_id": str(prop.id)},
            commit=False,
        )
    if commit and rows:
        db.commit()
