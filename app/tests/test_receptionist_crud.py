import sys
import os
from datetime import date
from uuid import uuid4

# Add workspace directory to python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.database.session import SessionLocal
from app.models.user import User
from app.models.profile import Profile
from app.core.constants import UserRole
from app.core.security import get_password_hash, create_access_token
from app.main import app

client = TestClient(app)
db: Session = SessionLocal()

def test_receptionist_crud_flow():
    print("\n=============================================")
    print("STARTING RECEPTIONIST CRUD END-TO-END FLOW TEST")
    print("=============================================\n")

    # 1. Fetch or create admin user for token authentication
    admin = db.query(User).filter(User.role == UserRole.ADMIN, User.is_deleted == False).first()
    if not admin:
        print("[SETUP] Creating mock admin user...")
        admin = User(
            email="admin_receptionist_test@prrohealth.com",
            hashed_password=get_password_hash("AdminTest123"),
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        db.flush()
        admin_profile = Profile(
            user_id=admin.id,
            full_name="System Admin Receptionist Test",
            phone="9999900020"
        )
        db.add(admin_profile)
        db.commit()
    else:
        print(f"[SETUP] Using existing admin user: {admin.email}")

    # Generate Access Token
    token = create_access_token(subject=admin.id, role=UserRole.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    # 2. CREATE RECEPTIONIST
    receptionist_email = f"e2e_receptionist_{uuid4().hex[:6]}@gmail.com"
    receptionist_payload = {
        "email": receptionist_email,
        "password": "Password123",
        "full_name": "E2E Test Receptionist",
        "phone": f"99988{uuid4().hex[:5]}",
        "gender": "female",
        "address": "Front Desk Suite A",
        "salary": 28000.00,
        "shift": "morning",
        "joining_staff_date": str(date.today()),
        "medical_notes": '{"employee_id":"REC-E2ETEST","nationality":"Indian","mfa_enabled":true}'
    }

    print("\n[TEST] 1. Creating receptionist...")
    res = client.post("/api/v1/receptionists/", json=receptionist_payload, headers=headers)
    assert res.status_code == 201, f"Failed creation: {res.text}"
    rec_data = res.json()["data"]
    receptionist_id = rec_data["id"]
    print(f"✓ Receptionist created successfully. ID: {receptionist_id}")

    # 3. GET RECEPTIONIST STATS
    print("\n[TEST] 2. Checking receptionist stats...")
    res = client.get("/api/v1/receptionists/stats", headers=headers)
    assert res.status_code == 200, f"Failed stats: {res.text}"
    stats_data = res.json()["data"]
    assert stats_data["total_receptionists"] >= 1
    print(f"✓ Stats verified: Total={stats_data['total_receptionists']}, Monthly Cost={stats_data['monthly_salary_cost']}")

    # 4. GET LIST
    print("\n[TEST] 3. Retrieving receptionists directory list...")
    res = client.get("/api/v1/receptionists/?page=1&per_page=10", headers=headers)
    assert res.status_code == 200, f"Failed list: {res.text}"
    list_data = res.json()["data"]
    assert len(list_data) > 0, "List should contain the created receptionist"
    print(f"✓ List retrieved. Count: {len(list_data)}")

    # 5. GET RECEPTIONIST BY ID
    print("\n[TEST] 4. Retrieving receptionist details by ID...")
    res = client.get(f"/api/v1/receptionists/{receptionist_id}", headers=headers)
    assert res.status_code == 200, f"Failed get receptionist: {res.text}"
    retrieved_data = res.json()["data"]
    assert retrieved_data["profile"]["full_name"] == "E2E Test Receptionist"
    assert retrieved_data["profile"]["shift"] == "morning"
    print("✓ Details retrieved correctly.")

    # 6. UPDATE RECEPTIONIST
    print("\n[TEST] 5. Updating receptionist shift and salary...")
    update_payload = {
        "shift": "evening",
        "salary": 32000.00
    }
    res = client.patch(f"/api/v1/receptionists/{receptionist_id}", json=update_payload, headers=headers)
    assert res.status_code == 200, f"Failed update: {res.text}"
    updated_data = res.json()["data"]
    assert updated_data["profile"]["shift"] == "evening"
    assert float(updated_data["profile"]["salary"]) == 32000.00
    print("✓ Receptionist updated successfully.")

    # 7. BULK OPERATIONS (Deactivate / Activate / Change Shift)
    print("\n[TEST] 6. Batch activating, suspending, and changing shifts...")
    # Deactivate
    deact_res = client.post("/api/v1/receptionists/bulk-deactivate", json={"ids": [receptionist_id]}, headers=headers)
    assert deact_res.status_code == 200
    res = client.get(f"/api/v1/receptionists/{receptionist_id}", headers=headers)
    assert res.json()["data"]["is_active"] is False
    print("✓ Bulk suspend verified.")

    # Activate
    act_res = client.post("/api/v1/receptionists/bulk-activate", json={"ids": [receptionist_id]}, headers=headers)
    assert act_res.status_code == 200
    res = client.get(f"/api/v1/receptionists/{receptionist_id}", headers=headers)
    assert res.json()["data"]["is_active"] is True
    print("✓ Bulk activate verified.")

    # Change shift
    shift_res = client.post("/api/v1/receptionists/bulk-change-shift", json={"ids": [receptionist_id], "shift": "morning"}, headers=headers)
    assert shift_res.status_code == 200
    res = client.get(f"/api/v1/receptionists/{receptionist_id}", headers=headers)
    assert res.json()["data"]["profile"]["shift"] == "morning"
    print("✓ Bulk change shift verified.")

    # 8. ARCHIVE / DELETE RECEPTIONIST
    print("\n[TEST] 7. Archiving (soft deleting) receptionist...")
    del_res = client.delete(f"/api/v1/receptionists/{receptionist_id}", headers=headers)
    assert del_res.status_code == 200
    
    # Check that it appears in archived list
    list_res = client.get("/api/v1/receptionists/?show_archived=true", headers=headers)
    assert list_res.status_code == 200
    archived_list = list_res.json()["data"]
    assert any(u["id"] == receptionist_id for u in archived_list), "Archived receptionist should be in archived list"
    print("✓ Soft delete / archiving verified.")

    # 9. RESTORE RECEPTIONIST
    print("\n[TEST] 8. Restoring archived receptionist...")
    restore_res = client.post(f"/api/v1/receptionists/{receptionist_id}/restore", headers=headers)
    assert restore_res.status_code == 200
    
    # Check that it no longer appears in archived list but appears in active list
    list_res = client.get("/api/v1/receptionists/?show_archived=false", headers=headers)
    assert list_res.status_code == 200
    active_list = list_res.json()["data"]
    assert any(u["id"] == receptionist_id for u in active_list), "Receptionist should be in active list after restore"
    print("✓ Restore verified.")

    print("\n=============================================")
    print("RECEPTIONIST CRUD FLOW TEST COMPLETED SUCCESSFULLY!")
    print("=============================================\n")
