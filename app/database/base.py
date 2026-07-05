from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Naming convention for database constraints to ensure clean migrations
# and prevent migration generation errors across SQLite & PostgreSQL
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=naming_convention)


class Base(DeclarativeBase):
    """
    SQLAlchemy Declarative Base class
    All application models must inherit from this Base.
    """
    metadata = metadata


# Import all models to ensure they are registered on the Base metadata for Alembic discovery
from app.models import user, profile, member, trainer, plan, membership, payment, attendance, workout, diet, association, notification, password_reset, receipt, lead  # noqa: F401
