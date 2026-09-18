# app/core/database.py
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# Create engine using DATABASE_URL from settings
# pool_size/max_overflow: default SQLAlchemy pool (5 + 10 overflow = 15
# connections total) is fine for local dev but becomes the real bottleneck
# once many users have Saka/profile open at once — every 3s chat-poll tick
# (see profile.js CHAT_POLL_MS) checks out a connection, so a few hundred
# concurrent users can exhaust 15 slots and start queueing/timing out on
# totally unrelated endpoints. pool_recycle avoids handing out connections
# the DB host has silently dropped after sitting idle.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
    pool_recycle=1800,
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Create base class for models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -----------------------------------------------------------------------
# Schema bootstrap — this project has no Alembic/migrations set up, and
# Base.metadata.create_all() (called in main.py) only creates tables that
# don't exist yet; it silently does nothing for columns added to a model
# whose table already exists on disk. That's exactly the situation new
# columns (ticket_tier, ticket_code, gate_unlocked, etc.) land in on any
# database that already has data. This walks every mapped table/column
# pair and ADD COLUMNs whatever's missing, so upgrades are safe to run
# repeatedly and won't touch columns that already exist.
# -----------------------------------------------------------------------
def ensure_schema_upgrades(bind=None):
    bind = bind or engine
    inspector = inspect(bind)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # a brand-new table — create_all() already handled it
        existing_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing_columns:
                continue
            try:
                col_type = column.type.compile(dialect=bind.dialect)
            except Exception:
                col_type = "TEXT"

            # Always add new columns as NULLable, even if the model marks
            # them NOT NULL. Adding a NOT-NULL column with no default to a
            # table that already has rows fails outright on Postgres, and
            # the old behavior here was to silently skip it — which left
            # the ORM believing the column exists while the DB doesn't
            # have it, so *every* query touching that table blew up with
            # an UndefinedColumn 500 the next time it ran. A nullable
            # column existing beats a NOT-NULL column missing entirely;
            # the app-level code already treats these as optional anyway.
            default_clause = ""
            if column.default is not None and getattr(column.default, "is_scalar", False):
                try:
                    default_val = column.default.arg
                    if isinstance(default_val, bool):
                        default_clause = f" DEFAULT {str(default_val).upper()}"
                    elif isinstance(default_val, (int, float)):
                        default_clause = f" DEFAULT {default_val}"
                    elif isinstance(default_val, str):
                        default_clause = f" DEFAULT '{default_val}'"
                except Exception:
                    default_clause = ""

            ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}{default_clause}'
            try:
                with bind.begin() as conn:
                    conn.execute(text(ddl))
                print(f"Schema upgrade: added {table.name}.{column.name}")
            except Exception as e:
                # Column may already exist under a race, or the type/DDL
                # itself is invalid for this dialect — log and keep going
                # rather than take the whole app down on boot.
                print(f"Schema upgrade skipped for {table.name}.{column.name}: {e}")

        # Same idea for indexes: create_all() won't add an index to a table
        # that already exists, so any Index(...) or Column(index=True) added
        # after go-live needs to be created explicitly here too.
        existing_indexes = {ix["name"] for ix in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in existing_indexes:
                continue
            try:
                index.create(bind=bind)
                print(f"Schema upgrade: created index {index.name}")
            except Exception as e:
                print(f"Schema upgrade skipped for index {index.name}: {e}")

        # Fix stale foreign keys — a column whose model definition points
        # at a different table than what's actually enforced in the DB.
        # This is exactly how withdrawals.admin_id ended up FK'd to the
        # unused `admins` table (an old auth design) while every actual
        # admin action writes a users.id into it: Postgres rejected the
        # write outright with an unhandled 500 on every "Message"/"Mark
        # Paid" admin action. ADD COLUMN above never runs for a column
        # that already exists, so a bad FK put in place before this model
        # was fixed would otherwise stay broken forever. This walks every
        # FK the model declares and repoints the DB constraint if it
        # doesn't match, dropping + recreating it.
        try:
            existing_fks = inspector.get_foreign_keys(table.name)
        except Exception:
            existing_fks = []
        existing_fk_by_column = {}
        for fk in existing_fks:
            cols = tuple(fk.get("constrained_columns") or [])
            if cols:
                existing_fk_by_column[cols] = fk

        for column in table.columns:
            for fk_def in column.foreign_keys:
                target_table = fk_def.column.table.name
                key = (column.name,)
                actual = existing_fk_by_column.get(key)
                if actual is None:
                    continue  # column itself was just added above, or has no FK yet — create_all/ADD COLUMN path handles it
                if actual.get("referred_table") == target_table:
                    continue  # already correct
                constraint_name = actual.get("name")
                try:
                    with bind.begin() as conn:
                        if constraint_name:
                            conn.execute(text(
                                f'ALTER TABLE "{table.name}" DROP CONSTRAINT "{constraint_name}"'
                            ))
                        conn.execute(text(
                            f'ALTER TABLE "{table.name}" ADD CONSTRAINT "{table.name}_{column.name}_fkey" '
                            f'FOREIGN KEY ("{column.name}") REFERENCES "{target_table}" ("{fk_def.column.name}")'
                        ))
                    print(
                        f"Schema upgrade: repointed FK {table.name}.{column.name} "
                        f"from {actual.get('referred_table')} to {target_table}"
                    )
                except Exception as e:
                    print(f"Schema upgrade skipped for FK {table.name}.{column.name}: {e}")