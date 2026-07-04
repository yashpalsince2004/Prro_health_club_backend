"""
Standalone cron script — calls ExpiryService directly.
Usage: python -m app.scripts.expiry_check

Set up on Render as a Cron Job:
  Schedule: 0 8 * * *   (every day at 8:00 AM IST)
  Command: python -m app.scripts.expiry_check
"""
from loguru import logger
from app.database.session import SessionLocal
from app.services.expiry_service import ExpiryService

def main():
    logger.info("Starting standalone membership expiry check script...")
    db = SessionLocal()
    try:
        service = ExpiryService(db)
        result = service.run_expiry_check(background_tasks=None)
        logger.info(f"Expiry check complete: {result}")
    except Exception as e:
        logger.error(f"Error running membership expiry check script: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    main()
