from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base
from app.database.mixins import UUIDMixin

class ReceiptsCounter(Base, UUIDMixin):
    """
    Simple DB table holding one row per year with the current count.
    """
    __tablename__ = "receipts_counter"
    __table_args__ = (
        {"comment": "Stores sequence counters for payment receipt generation"},
    )
    
    year: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    last_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
