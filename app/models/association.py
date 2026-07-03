"""
SQLAlchemy association tables for many-to-many relationships.
Includes trainer-member link tracking.
"""

from datetime import datetime, timezone
from sqlalchemy import Table, Column, ForeignKey, DateTime, Boolean, Uuid
from app.database.base import Base


# trainer_members association table
trainer_members = Table(
    "trainer_members",
    Base.metadata,
    Column(
        "trainer_id",
        Uuid,
        ForeignKey("trainers.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="Foreign key referencing the trainer id"
    ),
    Column(
        "member_id",
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        comment="Foreign key referencing the member id"
    ),
    Column(
        "assigned_at",
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp when the trainer was assigned to the member"
    ),
    Column(
        "is_active",
        Boolean,
        default=True,
        nullable=False,
        comment="Status flag indicating if the trainer assignment is currently active"
    ),
    comment="Association table linking trainers to their assigned members"
)
