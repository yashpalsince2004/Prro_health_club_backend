import sys
import os
from datetime import date, timedelta
from uuid import uuid4

# Add workspace directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.user import User
from app.models.profile import Profile
from app.models.trainer import Trainer
from app.models.plan import MembershipPlan
from app.models.member import Member
from app.core.constants import UserRole
from app.core.security import get_password_hash, create_access_token
from app.main import app

client = TestClient(app)
db: Session = SessionLocal()

def test_member_crud_flow():
    print("\n==========================================")
    print("STARTING MEMBER CRUD END-TO-END FLOW TEST")
    print("==========================================\n")

    # 1. Fetch or create admin user for token authentication
    admin = db.query(User).filter(User.role == UserRole.ADMIN, User.is_deleted == False).first()
    if not admin:
        print("[SETUP] Creating mock admin user...")
        admin = User(
            email="admin_test@prrohealth.com",
            hashed_password=get_password_hash("AdminTest123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.flush()
        admin_profile = Profile(
            user_id=admin.id,
            full_name="System Admin Test",
            phone="9999900000"
        )
        db.add(admin_profile)
        db.commit()
    else:
        print(f"[SETUP] Using existing admin user: {admin.email}")

    # Generate Access Token
    token = create_access_token(subject=admin.id, role=UserRole.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Fetch or create a Membership Plan
    plan = db.query(MembershipPlan).filter(MembershipPlan.is_active == True, MembershipPlan.is_deleted == False).first()
    if not plan:
        print("[SETUP] Creating mock membership plan...")
        plan = MembershipPlan(
            name="E2E Basic Monthly Plan",
            duration_days=30,
            price=1999.00,
            currency="INR",
            is_active=True
        )
        db.add(plan)
        db.commit()
    else:
        print(f"[SETUP] Using existing membership plan: {plan.name}")

    # 3. Fetch or create a Trainer
    trainer = db.query(Trainer).filter(Trainer.is_available == True, Trainer.is_deleted == False).first()
    if not trainer:
        print("[SETUP] Creating mock trainer...")
        trainer_user = User(
            email="trainer_test@prrohealth.com",
            hashed_password=get_password_hash("TrainerTest123"),
            role=UserRole.TRAINER,
            is_active=True
        )
        db.add(trainer_user)
        db.flush()
        trainer_profile = Profile(
            user_id=trainer_user.id,
            full_name="Trainer Test Coach",
            phone="9999900001"
        )
        db.add(trainer_profile)
        db.flush()
        trainer = Trainer(
            profile_id=trainer_profile.id,
            specialization="Strength & Conditioning",
            experience_years=5,
            is_available=True
        )
        db.add(trainer)
        db.commit()
    else:
        print(f"[SETUP] Using existing trainer: {trainer.profile.full_name}")

    # 4. CREATE MEMBER
    member_email = f"e2e_member_{uuid4().hex[:6]}@gmail.com"
    member_payload = {
        "email": member_email,
        "password": "Password123",
        "full_name": "E2E Test Member",
        "phone": f"99999{uuid4().hex[:5]}",
        "joining_date": str(date.today()),
        "plan_id": str(plan.id),
        "trainer_id": str(trainer.id),
        "notes": "Initial E2E test setup notes."
    }

    print("\n[TEST] 1. Creating member...")
    res = client.post("/api/v1/members/", json=member_payload, headers=headers)
    assert res.status_code == 201, f"Failed creation: {res.text}"
    member_data = res.json()["data"]
    member_id = member_data["id"]
    print(f"✓ Member created successfully. ID: {member_id}")

    # 5. GET MEMBERS STATS
    print("\n[TEST] 2. Checking member stats...")
    res = client.get("/api/v1/members/stats", headers=headers)
    assert res.status_code == 200, f"Failed stats: {res.text}"
    stats_data = res.json()["data"]
    print(f"✓ Stats verified: Total={stats_data['total_members']}, Active={stats_data['active_members']}")

    # 6. GET LIST
    print("\n[TEST] 3. Retrieving members directory list...")
    res = client.get("/api/v1/members/?page=1&per_page=10", headers=headers)
    assert res.status_code == 200, f"Failed list: {res.text}"
    list_data = res.json()["data"]
    assert len(list_data) > 0, "List should contain the created member"
    print(f"✓ List retrieved. Count: {len(list_data)}")

    # 7. GET MEMBER BY ID
    print("\n[TEST] 4. Retrieving member details by ID...")
    res = client.get(f"/api/v1/members/{member_id}", headers=headers)
    assert res.status_code == 200, f"Failed get member: {res.text}"
    retrieved_data = res.json()["data"]
    assert retrieved_data["profile"]["full_name"] == "E2E Test Member"
    print("✓ Member details retrieved correctly.")

    # 8. UPDATE MEMBER
    print("\n[TEST] 5. Updating member notes...")
    update_payload = {
        "notes": "Updated E2E test member notes."
    }
    res = client.patch(f"/api/v1/members/{member_id}", json=update_payload, headers=headers)
    assert res.status_code == 200, f"Failed update: {res.text}"
    updated_data = res.json()["data"]
    assert updated_data["notes"] == "Updated E2E test member notes."
    print("✓ Member notes updated successfully.")

    # 9. ARCHIVE MEMBER
    print("\n[TEST] 6. Archiving member...")
    res = client.delete(f"/api/v1/members/{member_id}", headers=headers)
    assert res.status_code == 200, f"Failed archive: {res.text}"
    print("✓ Member archived (soft deleted) successfully.")

    # Verify archived list
    res = client.get("/api/v1/members/?show_archived=true", headers=headers)
    assert res.status_code == 200
    archived_list = res.json()["data"]
    assert any(m["id"] == member_id for m in archived_list), "Archived member should appear in archived list"
    print("✓ Soft delete verification: member is in archived list.")

    # 10. RESTORE MEMBER
    print("\n[TEST] 7. Restoring member...")
    res = client.post(f"/api/v1/members/{member_id}/restore", headers=headers)
    assert res.status_code == 200, f"Failed restore: {res.text}"
    print("✓ Member restored successfully.")

    # 11. BULK OPERATIONS
    print("\n[TEST] 8. Executing bulk archive...")
    res = client.post("/api/v1/members/bulk-archive", json={"ids": [member_id]}, headers=headers)
    assert res.status_code == 200, f"Failed bulk archive: {res.text}"
    print("✓ Bulk archive succeeded.")

    print("\n[TEST] 9. Executing bulk restore...")
    res = client.post("/api/v1/members/bulk-restore", json={"ids": [member_id]}, headers=headers)
    assert res.status_code == 200, f"Failed bulk restore: {res.text}"
    print("✓ Bulk restore succeeded.")

    # 12. DUPLICATE MEMBER VALIDATION TESTS
    print("\n[TEST] 10. Testing duplicate validation constraints...")
    
    test_email = f"duplicate_check_{uuid4().hex[:6]}@gmail.com"
    test_phone = f"88888{uuid4().hex[:5]}"
    payload_a = {
        "email": test_email,
        "password": "Password123",
        "full_name": "Unique Name A",
        "phone": test_phone,
        "joining_date": str(date.today()),
        "plan_id": str(plan.id),
        "trainer_id": str(trainer.id)
    }
    res = client.post("/api/v1/members/", json=payload_a, headers=headers)
    assert res.status_code == 201

    # Case 1: Same Name, DIFFERENT Email, DIFFERENT Phone -> Should Succeed (Name is NOT unique)
    payload_same_name = {
        "email": f"diff_email_{uuid4().hex[:6]}@gmail.com",
        "password": "Password123",
        "full_name": "Unique Name A",
        "phone": f"77777{uuid4().hex[:5]}",
        "joining_date": str(date.today()),
        "plan_id": str(plan.id),
        "trainer_id": str(trainer.id)
    }
    res = client.post("/api/v1/members/", json=payload_same_name, headers=headers)
    assert res.status_code == 201
    print("✓ Verification: Name is not unique (different email/phone created successfully)")

    # Case 2: Same Email, DIFFERENT Phone -> Should Fail with "Email already registered."
    payload_same_email = {
        "email": test_email,
        "password": "Password123",
        "full_name": "Different Name",
        "phone": f"66666{uuid4().hex[:5]}",
        "joining_date": str(date.today()),
        "plan_id": str(plan.id),
        "trainer_id": str(trainer.id)
    }
    res = client.post("/api/v1/members/", json=payload_same_email, headers=headers)
    assert res.status_code == 409
    assert res.json()["error"]["message"] == "Email already registered."
    print("✓ Verification: Email uniqueness check returned 'Email already registered.'")

    # Case 3: DIFFERENT Email, Same Phone -> Should Fail with "Phone number already registered."
    payload_same_phone = {
        "email": f"diff_email2_{uuid4().hex[:6]}@gmail.com",
        "password": "Password123",
        "full_name": "Different Name",
        "phone": test_phone,
        "joining_date": str(date.today()),
        "plan_id": str(plan.id),
        "trainer_id": str(trainer.id)
    }
    res = client.post("/api/v1/members/", json=payload_same_phone, headers=headers)
    assert res.status_code == 409
    assert res.json()["error"]["message"] == "Phone number already registered."
    print("✓ Verification: Phone uniqueness check returned 'Phone number already registered.'")

    # Case 4: Same Email, Same Phone -> Should Fail with "An account with this email and phone number already exists."
    payload_both_dup = {
        "email": test_email,
        "password": "Password123",
        "full_name": "Different Name",
        "phone": test_phone,
        "joining_date": str(date.today()),
        "plan_id": str(plan.id),
        "trainer_id": str(trainer.id)
    }
    res = client.post("/api/v1/members/", json=payload_both_dup, headers=headers)
    assert res.status_code == 409
    assert res.json()["error"]["message"] == "An account with this email and phone number already exists."
    print("✓ Verification: Combined duplicate email/phone check returned correct details.")

    print("\n==========================================")
    print("ALL END-TO-END FLOW TESTS COMPLETED")
    print("STATUS: 100% SUCCESS")
    print("==========================================\n")

if __name__ == "__main__":
    try:
        test_member_crud_flow()
    except AssertionError as ae:
        print(f"\n❌ TEST FAILURE: {str(ae)}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ UNEXPECTED TEST ERROR: {str(e)}")
        sys.exit(1)
    finally:
        db.close()
