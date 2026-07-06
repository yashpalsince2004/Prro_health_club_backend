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
from app.models.member import Member
from app.core.constants import UserRole
from app.core.security import get_password_hash, create_access_token
from app.main import app

client = TestClient(app)
db: Session = SessionLocal()

def test_trainer_crud_flow():
    print("\n==========================================")
    print("STARTING TRAINER CRUD END-TO-END FLOW TEST")
    print("==========================================\n")

    # 1. Fetch or create admin user for token authentication
    admin = db.query(User).filter(User.role == UserRole.ADMIN, User.is_deleted == False).first()
    if not admin:
        print("[SETUP] Creating mock admin user...")
        admin = User(
            email="admin_trainer_test@prrohealth.com",
            hashed_password=get_password_hash("AdminTest123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.flush()
        admin_profile = Profile(
            user_id=admin.id,
            full_name="System Admin Trainer Test",
            phone="9999900010"
        )
        db.add(admin_profile)
        db.commit()
    else:
        print(f"[SETUP] Using existing admin user: {admin.email}")

    # Generate Access Token
    token = create_access_token(subject=admin.id, role=UserRole.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. CREATE TRAINER
    emp_id = f"EMP-{uuid4().hex[:6].upper()}"
    trainer_email = f"e2e_trainer_{uuid4().hex[:6]}@gmail.com"
    trainer_payload = {
        "email": trainer_email,
        "password": "Password123",
        "full_name": "E2E Test Trainer",
        "phone": f"99999{uuid4().hex[:5]}",
        "employee_id": emp_id,
        "specialization": "Bodybuilding",
        "specializations": ["Bodybuilding", "Strength Training"],
        "experience_years": 4,
        "qualification": "B.Sc. Exercise Science",
        "certifications": ["ACE Certified", "NASM CPT"],
        "bio": "Certified personal trainer dedicated to bodybuilding goals.",
        "employment_type": "Full Time",
        "salary": 45000.00,
        "salary_type": "Monthly",
        "shift": "Morning",
        "joining_staff_date": str(date.today()),
        "max_members": 2,
        "working_days": ["Monday", "Wednesday", "Friday"],
        "working_hours": "06:00 - 14:00"
    }

    print("\n[TEST] 1. Creating trainer...")
    res = client.post("/api/v1/trainers/", json=trainer_payload, headers=headers)
    assert res.status_code == 201, f"Failed creation: {res.text}"
    trainer_data = res.json()["data"]
    trainer_id = trainer_data["id"]
    print(f"✓ Trainer created successfully. ID: {trainer_id}")

    # 3. GET TRAINER STATS
    print("\n[TEST] 2. Checking trainer stats...")
    res = client.get("/api/v1/trainers/stats", headers=headers)
    assert res.status_code == 200, f"Failed stats: {res.text}"
    stats_data = res.json()["data"]
    print(f"✓ Stats verified: Total={stats_data['total_trainers']}, Active={stats_data['active_trainers']}")

    # 4. GET LIST
    print("\n[TEST] 3. Retrieving trainers directory list...")
    res = client.get("/api/v1/trainers/?page=1&per_page=10", headers=headers)
    assert res.status_code == 200, f"Failed list: {res.text}"
    list_data = res.json()["data"]
    assert len(list_data) > 0, "List should contain the created trainer"
    print(f"✓ List retrieved. Count: {len(list_data)}")

    # 5. GET TRAINER BY ID
    print("\n[TEST] 4. Retrieving trainer details by ID...")
    res = client.get(f"/api/v1/trainers/{trainer_id}", headers=headers)
    assert res.status_code == 200, f"Failed get trainer: {res.text}"
    retrieved_data = res.json()["data"]
    assert retrieved_data["employee_id"] == emp_id
    assert retrieved_data["profile"]["full_name"] == "E2E Test Trainer"
    print("✓ Trainer details retrieved correctly.")

    # 6. UPDATE TRAINER
    print("\n[TEST] 5. Updating trainer specs...")
    update_payload = {
        "max_members": 3,
        "qualification": "M.Sc. Exercise Science"
    }
    res = client.patch(f"/api/v1/trainers/{trainer_id}", json=update_payload, headers=headers)
    assert res.status_code == 200, f"Failed update: {res.text}"
    updated_data = res.json()["data"]
    assert updated_data["max_members"] == 3
    assert updated_data["qualification"] == "M.Sc. Exercise Science"
    print("✓ Trainer updated successfully.")

    # 7. CAPACITY VALIDATION & ASSIGNMENT
    print("\n[TEST] 6. Creating members to test capacity...")
    # Create two members
    members = []
    for i in range(4):
        member_email = f"e2e_assign_member_{i}_{uuid4().hex[:6]}@gmail.com"
        member_payload = {
            "email": member_email,
            "password": "Password123",
            "full_name": f"E2E Assign Member {i}",
            "phone": f"98989{uuid4().hex[:5]}",
            "joining_date": str(date.today()),
            "notes": "Coaching assignment test member."
        }
        member_res = client.post("/api/v1/members/", json=member_payload, headers=headers)
        assert member_res.status_code == 201, f"Failed member creation: {member_res.text}"
        members.append(member_res.json()["data"])

    # Update trainer capacity to 2 to test validation limit
    client.patch(f"/api/v1/trainers/{trainer_id}", json={"max_members": 2}, headers=headers)

    # Assign member 0
    print("[TEST] Assigning first member to trainer (Capacity = 1 / 2)")
    assign_res = client.post(f"/api/v1/trainers/{trainer_id}/assign-member", json={"member_id": members[0]["id"]}, headers=headers)
    assert assign_res.status_code == 200, f"Failed assign member 0: {assign_res.text}"

    # Assign member 1
    print("[TEST] Assigning second member to trainer (Capacity = 2 / 2)")
    assign_res = client.post(f"/api/v1/trainers/{trainer_id}/assign-member", json={"member_id": members[1]["id"]}, headers=headers)
    assert assign_res.status_code == 200, f"Failed assign member 1: {assign_res.text}"

    # Assign member 2 (Should Fail due to Max Capacity)
    print("[TEST] Assigning third member to trainer (Should Fail - capacity exceeded)")
    assign_res = client.post(f"/api/v1/trainers/{trainer_id}/assign-member", json={"member_id": members[2]["id"]}, headers=headers)
    assert assign_res.status_code == 409, f"Assign should fail with 409 Conflict: {assign_res.status_code}"
    assert "maximum capacity" in assign_res.json()["error"]["message"]
    print("✓ Capacity check successfully blocked assignment.")

    # Bulk Assign Member 2 and 3 to Trainer (Should also Fail)
    print("[TEST] Bulk assigning members (Should Fail - capacity exceeded)")
    bulk_assign_res = client.post("/api/v1/members/bulk-assign-trainer", json={
        "member_ids": [members[2]["id"], members[3]["id"]],
        "trainer_id": trainer_id
    }, headers=headers)
    assert bulk_assign_res.status_code == 409, f"Bulk assign should fail: {bulk_assign_res.text}"
    assert "capacity limit" in bulk_assign_res.json()["error"]["message"]
    print("✓ Bulk assign capacity check successfully blocked assignment.")

    # 8. BULK OPERATIONS (Activate / Suspend)
    print("\n[TEST] 7. Batch activating and suspending trainers...")
    # Deactivate trainer
    deact_res = client.post("/api/v1/trainers/bulk-deactivate", json={"ids": [trainer_id]}, headers=headers)
    assert deact_res.status_code == 200
    res = client.get(f"/api/v1/trainers/{trainer_id}", headers=headers)
    assert res.json()["data"]["is_active"] is False
    print("✓ Bulk suspend verified.")

    # Activate trainer
    act_res = client.post("/api/v1/trainers/bulk-activate", json={"ids": [trainer_id]}, headers=headers)
    assert act_res.status_code == 200
    res = client.get(f"/api/v1/trainers/{trainer_id}", headers=headers)
    assert res.json()["data"]["is_active"] is True
    print("✓ Bulk activate verified.")

    # 9. ARCHIVE / DELETE TRAINER
    print("\n[TEST] 8. Archiving (soft deleting) trainer...")
    del_res = client.delete(f"/api/v1/trainers/{trainer_id}", headers=headers)
    assert del_res.status_code == 200
    
    # Check that it appears in archived list
    list_res = client.get("/api/v1/trainers/?show_archived=true", headers=headers)
    assert list_res.status_code == 200
    archived_list = list_res.json()["data"]
    assert any(t["id"] == trainer_id for t in archived_list), "Archived trainer should be in archived list"
    print("✓ Soft delete / archiving verified.")

    # 10. RESTORE TRAINER
    print("\n[TEST] 9. Restoring archived trainer...")
    restore_res = client.post(f"/api/v1/trainers/{trainer_id}/restore", headers=headers)
    assert restore_res.status_code == 200
    
    # Check that it no longer appears in archived list but appears in active list
    list_res = client.get("/api/v1/trainers/?show_archived=false", headers=headers)
    assert list_res.status_code == 200
    active_list = list_res.json()["data"]
    assert any(t["id"] == trainer_id for t in active_list), "Trainer should be in active list after restore"
    print("✓ Restore verified.")

    print("\n==========================================")
    print("TRAINER CRUD FLOW TEST COMPLETED SUCCESSFULLY!")
    print("==========================================\n")
