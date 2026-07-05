import sys
from loguru import logger
from app.database.session import SessionLocal
from app.models.gym_settings import GymSettings

default_settings = [
    # General
    {"key": "gym_name",      "value": "Prro Health Club", "category": "general", "label": "Gym Name", "description": "Display name of the gym brand"},
    {"key": "gym_phone",     "value": "+91 99999 88888",  "category": "general", "label": "Phone Number", "description": "Customer support contact helpline"},
    {"key": "gym_email",     "value": "support@prrohealth.com", "category": "general", "label": "Email Address", "description": "Official brand email inbox"},
    {"key": "gym_address",   "value": "Gold's Hub, Bandra West, Mumbai, MH, 400050", "category": "general", "label": "Address", "description": "Physical facility location details"},
    {"key": "gym_website",   "value": "https://prrohealth.com", "category": "general", "label": "Website URL", "description": "Public brand website URL link"},
    
    # Finance
    {"key": "gst_number",    "value": "27AAAAA1111A1Z1",  "category": "finance", "label": "GST Registration Number", "description": "Goods & Services Tax Registration Number ID"},
    {"key": "gst_percent",   "value": "18",                "category": "finance", "label": "GST Percentage", "description": "Default tax surcharge percentage value"},
    {"key": "currency",      "value": "INR",               "category": "finance", "label": "Currency", "description": "Default currency code (e.g. INR, USD)"},
    
    # Working Hours
    {"key": "opening_time",  "value": "06:00",             "category": "hours",   "label": "Opening Time", "description": "Facility opening hours time"},
    {"key": "closing_time",  "value": "22:00",             "category": "hours",   "label": "Closing Time", "description": "Facility closing hours time"},
    {"key": "working_days",  "value": "Mon,Tue,Wed,Thu,Fri,Sat", "category": "hours", "label": "Working Days", "description": "Operational working days list (comma separated)"},
    
    # Notifications  
    {"key": "expiry_reminder_days", "value": "7",          "category": "notifications", "label": "Membership Expiry Reminder (days before)", "description": "Days before expiry to trigger warning alert emails"},
    {"key": "send_welcome_email",   "value": "true",       "category": "notifications", "label": "Send Welcome Email to New Members", "description": "Send credentials welcome email upon registration"},
    {"key": "send_payment_receipt", "value": "true",       "category": "notifications", "label": "Send Payment Receipt Email", "description": "Send payment success receipt invoice attachment emails"},
]

def seed_gym_settings():
    db = SessionLocal()
    try:
        logger.info("Seeding gym operational settings...")
        for setting in default_settings:
            existing = db.query(GymSettings).filter(GymSettings.key == setting["key"]).first()
            if not existing:
                new_setting = GymSettings(
                    key=setting["key"],
                    value=setting["value"],
                    category=setting["category"],
                    label=setting["label"],
                    description=setting["description"]
                )
                db.add(new_setting)
        db.commit()
        logger.info("Gym operational settings seeded successfully.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding gym settings: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    seed_gym_settings()
