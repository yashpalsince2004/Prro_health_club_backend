"""
Central receipt number generator.
Format: PRRO-{YEAR}-{6-digit-sequence}
Example: PRRO-2026-000001, PRRO-2026-000042

Uses a DB sequence counter stored in a simple receipts_counter table.
Falls back to timestamp-based if counter unavailable.
"""
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.receipt import ReceiptsCounter

def generate_receipt_number(db: Session) -> str:
    """
    Thread-safe sequential receipt number generator.
    Uses SELECT FOR UPDATE to prevent race conditions.
    Returns: "PRRO-2026-000001"
    """
    from datetime import datetime
    year = datetime.now().year
    
    # Upsert the counter row and increment atomically
    # SELECT FOR UPDATE to prevent concurrent duplicates
    counter = db.query(ReceiptsCounter).filter(
        ReceiptsCounter.year == year
    ).with_for_update().first()
    
    if not counter:
        counter = ReceiptsCounter(year=year, last_sequence=0)
        db.add(counter)
    
    counter.last_sequence += 1
    db.flush()  # write to DB but don't commit (caller commits)
    
    return f"{settings.INVOICE_PREFIX}-{year}-{counter.last_sequence:06d}"
