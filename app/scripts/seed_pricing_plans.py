import sys
import os

# Add workspace directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database.session import SessionLocal
from app.models.plan import MembershipPlan
from app.models.pt_plan import PTPlan
from app.models.locker_plan import LockerPlan
from app.models.additional_service import AdditionalService


def seed_pricing():
    db = SessionLocal()
    try:
        print("Seeding Membership Plans...")
        # 1. Membership Plans definitions
        memberships_data = [
            # Category 1: CrossFit + Weight Training
            {
                "name": "CrossFit + Weight Training (1 Month)",
                "category": "CrossFit + Weight Training",
                "duration_days": 30,
                "price": 800.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#E65100",
                "display_order": 1,
                "features": ["CrossFit Access", "Weight Training Area", "General Trainer Guidance"]
            },
            {
                "name": "CrossFit + Weight Training (3 Months)",
                "category": "CrossFit + Weight Training",
                "duration_days": 90,
                "price": 2000.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#E65100",
                "display_order": 2,
                "features": ["CrossFit Access", "Weight Training Area", "General Trainer Guidance"]
            },
            {
                "name": "CrossFit + Weight Training (6 Months)",
                "category": "CrossFit + Weight Training",
                "duration_days": 180,
                "price": 3600.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#E65100",
                "display_order": 3,
                "features": ["CrossFit Access", "Weight Training Area", "General Trainer Guidance"]
            },
            {
                "name": "CrossFit + Weight Training (1 Year)",
                "category": "CrossFit + Weight Training",
                "duration_days": 365,
                "price": 6000.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#E65100",
                "display_order": 4,
                "features": ["CrossFit Access", "Weight Training Area", "General Trainer Guidance", "Free BMI Check"]
            },

            # Category 2: Only Cardio
            {
                "name": "Only Cardio (1 Month)",
                "category": "Only Cardio",
                "duration_days": 30,
                "price": 1500.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#0288D1",
                "display_order": 5,
                "features": ["Cardio Zone Access", "Treadmills & Ellipticals Only"]
            },
            {
                "name": "Only Cardio (3 Months)",
                "category": "Only Cardio",
                "duration_days": 90,
                "price": 3500.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#0288D1",
                "display_order": 6,
                "features": ["Cardio Zone Access", "Treadmills & Ellipticals Only"]
            },
            {
                "name": "Only Cardio (6 Months)",
                "category": "Only Cardio",
                "duration_days": 180,
                "price": 6000.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#0288D1",
                "display_order": 7,
                "features": ["Cardio Zone Access", "Treadmills & Ellipticals Only"]
            },
            {
                "name": "Only Cardio (1 Year)",
                "category": "Only Cardio",
                "duration_days": 365,
                "price": 9000.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#0288D1",
                "display_order": 8,
                "features": ["Cardio Zone Access", "Treadmills & Ellipticals Only"]
            },

            # Category 3: Cardio + CrossFit + Weight Training
            {
                "name": "Cardio + CrossFit + Weight Training (1 Month)",
                "category": "Cardio + CrossFit + Weight Training",
                "duration_days": 30,
                "price": 1200.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#7B1FA2",
                "display_order": 9,
                "features": ["Full Gym Access", "Cardio Zone", "CrossFit Area", "Weight Training"]
            },
            {
                "name": "Cardio + CrossFit + Weight Training (3 Months)",
                "category": "Cardio + CrossFit + Weight Training",
                "duration_days": 90,
                "price": 3000.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#7B1FA2",
                "display_order": 10,
                "features": ["Full Gym Access", "Cardio Zone", "CrossFit Area", "Weight Training"]
            },
            {
                "name": "Cardio + CrossFit + Weight Training (6 Months)",
                "category": "Cardio + CrossFit + Weight Training",
                "duration_days": 180,
                "price": 5500.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#7B1FA2",
                "display_order": 11,
                "features": ["Full Gym Access", "Cardio Zone", "CrossFit Area", "Weight Training"]
            },
            {
                "name": "Cardio + CrossFit + Weight Training (1 Year)",
                "category": "Cardio + CrossFit + Weight Training",
                "duration_days": 365,
                "price": 9999.00,
                "admission_fee": 200.00,
                "tax": 18.00,
                "color": "#7B1FA2",
                "display_order": 12,
                "features": ["Full Gym Access", "Cardio Zone", "CrossFit Area", "Weight Training", "Free Locker Setup"]
            }
        ]

        for p in memberships_data:
            existing = db.query(MembershipPlan).filter(MembershipPlan.name == p["name"], MembershipPlan.is_deleted == False).first()
            if not existing:
                plan = MembershipPlan(
                    name=p["name"],
                    category=p["category"],
                    duration_days=p["duration_days"],
                    price=p["price"],
                    admission_fee=p["admission_fee"],
                    tax=p["tax"],
                    color=p["color"],
                    display_order=p["display_order"],
                    features=p["features"],
                    is_active=True
                )
                db.add(plan)
                print(f"Added plan: {p['name']}")
            else:
                # Update existing columns if plan already in database
                existing.category = p["category"]
                existing.admission_fee = p["admission_fee"]
                existing.tax = p["tax"]
                existing.color = p["color"]
                existing.display_order = p["display_order"]
                print(f"Updated plan metadata: {p['name']}")

        print("\nSeeding PT Packages...")
        # 2. PT Packages definitions
        pt_data = [
            {
                "package_name": "Silver",
                "price": 4000.00,
                "session_count": 12,
                "whatsapp_support": False,
                "locker_included": False,
                "transformation_included": False,
                "diet_included": True,
                "stretching_included": True,
                "supplement_guidance": True,
                "description": "Base Certified Trainer support with diet and supplement guidance."
            },
            {
                "package_name": "Gold",
                "price": 5000.00,
                "session_count": 18,
                "whatsapp_support": False,
                "locker_included": False,
                "transformation_included": True,
                "diet_included": True,
                "stretching_included": True,
                "supplement_guidance": True,
                "description": "Transformation guidance with 15-18 sessions of dedicated focus."
            },
            {
                "package_name": "Platinum",
                "price": 6000.00,
                "session_count": 28,
                "whatsapp_support": True,
                "locker_included": True,
                "transformation_included": True,
                "diet_included": True,
                "stretching_included": True,
                "supplement_guidance": True,
                "description": "Functional Training, Locker included, transformation and 8 hrs WhatsApp support."
            }
        ]

        for p in pt_data:
            existing = db.query(PTPlan).filter(PTPlan.package_name == p["package_name"], PTPlan.is_deleted == False).first()
            if not existing:
                pt_p = PTPlan(
                    package_name=p["package_name"],
                    price=p["price"],
                    session_count=p["session_count"],
                    whatsapp_support=p["whatsapp_support"],
                    locker_included=p["locker_included"],
                    transformation_included=p["transformation_included"],
                    diet_included=p["diet_included"],
                    stretching_included=p["stretching_included"],
                    supplement_guidance=p["supplement_guidance"],
                    description=p["description"],
                    is_active=True
                )
                db.add(pt_p)
                print(f"Added PT plan: {p['package_name']}")
            else:
                existing.price = p["price"]
                existing.session_count = p["session_count"]
                existing.whatsapp_support = p["whatsapp_support"]
                existing.locker_included = p["locker_included"]
                existing.transformation_included = p["transformation_included"]
                existing.diet_included = p["diet_included"]
                existing.stretching_included = p["stretching_included"]
                existing.supplement_guidance = p["supplement_guidance"]
                print(f"Updated PT plan: {p['package_name']}")

        print("\nSeeding Locker Plans...")
        # 3. Locker plans
        locker_p = db.query(LockerPlan).filter(LockerPlan.is_deleted == False).first()
        if not locker_p:
            locker = LockerPlan(
                name="Standard Locker Plan",
                deposit=500.00,
                monthly_rent=250.00,
                quarterly_rent=600.00,
                late_fee=0.00,
                refundable=True,
                is_active=True
            )
            db.add(locker)
            print("Added Standard Locker Plan")
        else:
            locker_p.deposit = 500.00
            locker_p.monthly_rent = 250.00
            locker_p.quarterly_rent = 600.00
            print("Updated Standard Locker Plan rents")

        print("\nSeeding Additional Services...")
        # 4. Additional Services definitions
        services_data = [
            {"name": "Body Massage", "price": 500.00, "description": "Relaxing standard full body massage"},
            {"name": "Premium Massage", "price": 800.00, "description": "Premium therapeutic deep-tissue body massage"},
            {"name": "Nutrition Consultation", "price": 1200.00, "description": "Expert customized calorie/macro consultation"},
            {"name": "BMI Test", "price": 100.00, "description": "Standard Body Mass Index metric check"},
            {"name": "Body Fat Analysis", "price": 150.00, "description": "InBody analysis of body fat & skeletal muscle mass"}
        ]

        for s in services_data:
            existing = db.query(AdditionalService).filter(AdditionalService.name == s["name"], AdditionalService.is_deleted == False).first()
            if not existing:
                srv = AdditionalService(
                    name=s["name"],
                    price=s["price"],
                    description=s["description"],
                    is_active=True
                )
                db.add(srv)
                print(f"Added service: {s['name']}")
            else:
                existing.price = s["price"]
                print(f"Updated service price: {s['name']}")

        db.commit()
        print("\nDatabase Seeding Done Successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_pricing()
