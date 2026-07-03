"""
Standalone database seeding script to populate initial testing data.
"""

import sys
from datetime import date, timedelta
from loguru import logger

from app.database.session import SessionLocal
from app.core.security import get_password_hash
from app.core.constants import UserRole, SubscriptionStatus
from app.models.user import User
from app.models.profile import Profile
from app.models.member import Member
from app.models.trainer import Trainer
from app.models.plan import MembershipPlan
from app.models.membership import Membership


def seed_data() -> None:
    """Populates the database with initial users, plans, and profiles."""
    logger.info("Initializing database seed process...")
    db = SessionLocal()
    try:
        # 1. Check if seed data already exists (using Admin email as key)
        existing_admin = db.query(User).filter(User.email == "admin@prrohealthclub.com").first()
        if existing_admin:
            logger.warning("Database already seeded. Aborting to prevent duplicates.")
            return

        logger.info("Cleaning up old @ironcore.gym seed users if any exist...")
        old_users = db.query(User).filter(User.email.like("%@ironcore.gym")).all()
        for old_u in old_users:
            db.delete(old_u)
        db.flush()

        logger.info("Seeding system roles, users, and membership plans...")

        # 2. Create Users
        admin_user = User(
            email="admin@prrohealthclub.com",
            hashed_password=get_password_hash("Admin@123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        receptionist_user = User(
            email="reception@prrohealthclub.com",
            hashed_password=get_password_hash("Reception@123"),
            role=UserRole.RECEPTIONIST,
            is_active=True
        )
        trainer_user = User(
            email="trainer@prrohealthclub.com",
            hashed_password=get_password_hash("Trainer@123"),
            role=UserRole.TRAINER,
            is_active=True
        )
        member1_user = User(
            email="member1@prrohealthclub.com",
            hashed_password=get_password_hash("Member1@123"),
            role=UserRole.MEMBER,
            is_active=True
        )
        member2_user = User(
            email="member2@prrohealthclub.com",
            hashed_password=get_password_hash("Member2@123"),
            role=UserRole.MEMBER,
            is_active=True
        )

        db.add_all([admin_user, receptionist_user, trainer_user, member1_user, member2_user])
        db.flush()  # Generate user IDs for foreign keys

        # 3. Create Profiles
        admin_profile = Profile(
            user_id=admin_user.id,
            full_name="Admin User",
            phone="9999900001"
        )
        receptionist_profile = Profile(
            user_id=receptionist_user.id,
            full_name="Receptionist User",
            phone="9999900002"
        )
        trainer_profile = Profile(
            user_id=trainer_user.id,
            full_name="Trainer User",
            phone="9999900003"
        )
        member1_profile = Profile(
            user_id=member1_user.id,
            full_name="Member One",
            phone="9999900004",
            biometric_device_id=1  # Simulating device enrollment
        )
        member2_profile = Profile(
            user_id=member2_user.id,
            full_name="Member Two",
            phone="9999900005"
        )

        db.add_all([admin_profile, receptionist_profile, trainer_profile, member1_profile, member2_profile])
        db.flush()  # Generate profile IDs

        # 4. Create Trainer details
        trainer = Trainer(
            profile_id=trainer_profile.id,
            specialization="Strength & Conditioning",
            experience_years=5,
            certifications=["CSCS", "ACE-CPT"],
            bio="Dedicated trainer specializing in performance coaching and functional movement.",
            is_available=True
        )
        db.add(trainer)

        # 5. Create Members
        member1 = Member(
            profile_id=member1_profile.id,
            joining_date=date.today(),
            notes="Requires guidance on weight loss and hypertrophy."
        )
        member2 = Member(
            profile_id=member2_profile.id,
            joining_date=date.today(),
            notes="Experienced lifter looking for open gym access."
        )
        db.add_all([member1, member2])
        db.flush()

        # 6. Create or Get Membership Plans
        basic_plan = db.query(MembershipPlan).filter(MembershipPlan.name == "Basic Plan").first()
        if not basic_plan:
            basic_plan = MembershipPlan(
                name="Basic Plan",
                description="Access to basic gym facilities during standard hours",
                duration_days=30,
                price=1500.00,
                currency="INR",
                features=["Gym Access", "Locker Room Access"],
                is_active=True,
                display_order=1
            )
            db.add(basic_plan)

        premium_plan = db.query(MembershipPlan).filter(MembershipPlan.name == "Premium Plan").first()
        if not premium_plan:
            premium_plan = MembershipPlan(
                name="Premium Plan",
                description="Full facility access, trainer guidance, and diet templates",
                duration_days=30,
                price=2500.00,
                currency="INR",
                features=["Gym Access", "Trainer Support", "Diet Plan", "Steam Room Access"],
                is_active=True,
                display_order=2
            )
            db.add(premium_plan)

        annual_plan = db.query(MembershipPlan).filter(MembershipPlan.name == "Annual Plan").first()
        if not annual_plan:
            annual_plan = MembershipPlan(
                name="Annual Plan",
                description="Full-year premium access at highly discounted rates",
                duration_days=365,
                price=15000.00,
                currency="INR",
                features=["Gym Access", "Trainer Support", "Diet Plan", "Steam Room Access", "Complimentary T-Shirt"],
                is_active=True,
                display_order=3
            )
            db.add(annual_plan)
        
        db.flush()

        # 7. Create Membership for member1 linked to Premium Plan
        membership = Membership(
            member_id=member1.id,
            plan_id=premium_plan.id,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=premium_plan.duration_days),
            status=SubscriptionStatus.ACTIVE,
            auto_renew=False,
            discount_percent=0.00,
            notes="First month subscription"
        )
        db.add(membership)

        # 8. Assign Trainer to Member 1 (many-to-many relationship)
        trainer.assigned_members.append(member1)

        # Commit everything
        db.commit()
        logger.info("Database seeded successfully with test records.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding database: {str(e)}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
