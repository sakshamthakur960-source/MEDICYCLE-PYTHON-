"""Run an isolated SQLite API smoke test; it does not connect to the user's MySQL DB.
Run from the backend root: python tests/sqlite_smoke_test.py
"""
import os, sys, types
from pathlib import Path
PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)
from datetime import date, datetime
from sqlalchemy import create_engine, select
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

os.environ["JWT_SECRET"] = "local_sqlite_test_secret_with_at_least_32_characters"
class Base(DeclarativeBase):
    pass
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
database_stub = types.ModuleType("Database")
database_stub.engine = engine
database_stub.Base = Base
sys.modules["Database"] = database_stub
import models
Base.metadata.create_all(engine)
import api.main as api
client = TestClient(api.app)

def register(name, email):
    response = client.post("/api/auth/register", json={"fullName": name, "email": email, "password": "securepass123"})
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["accessToken"]}

customer_headers = register("Customer Demo", "customer@example.com")
staff_headers = register("Staff Demo", "staff@example.com")
with Session(engine) as db:
    facility = models.Facility(facilityName="Test Facility", facilityType="DISPOSAL", address="Test address", authorizationStatus="APPROVED", operatingStatus="ACTIVE")
    medicine = models.Medicine(name="Test Paracetamol", genericName="Paracetamol", manufacturer="Demo", strength="500mg", dosageForm="Tablet", barcode="TEST123")
    db.add_all([facility, medicine]); db.flush()
    slot = models.PickupSlot(facilityId=facility.facilityId, slotDate=date.today(), startTime=datetime(2026, 11, 22, 10), endTime=datetime(2026, 11, 22, 11), capacity=5, bookedCount=0, slotStatus="AVAILABLE")
    staff_user = db.scalar(select(models.User).where(models.User.email == "staff@example.com"))
    db.add(models.FacilityStaff(facilityId=facility.facilityId, userId=staff_user.userId, staffRole="INSPECTOR", employmentStatus="ACTIVE", joinedAt=datetime.utcnow()))
    db.add(slot); db.commit()
    medicine_id, slot_id, facility_id = medicine.medicineId, slot.pickupSlotId, facility.facilityId

address = client.post("/api/users/me/addresses", headers=customer_headers, json={"addressLine": "12 Test Road", "city": "Solan", "state": "Himachal Pradesh", "postalCode": "173212", "isDefault": True})
assert address.status_code == 201, address.text
return_response = client.post("/api/returns", headers=customer_headers, json={"returnMethod": "DOORSTEP_PICKUP", "addressId": address.json()["addressId"], "pickupSlotId": str(slot_id), "items": [{"medicineId": str(medicine_id), "quantity": 2, "packagingCondition": "SEALED"}]})
assert return_response.status_code == 201, return_response.text
return_id = return_response.json()["return"]["returnId"]
item_id = return_response.json()["items"][0]["returnItemId"]
intake = client.post(f"/api/staff/returns/{return_id}/intake", headers=staff_headers, json={"facilityId": str(facility_id), "intakeNotes": "received"})
assert intake.status_code == 201, intake.text
decision = client.post(f"/api/staff/returns/{return_id}/decision", headers=staff_headers, json={"decision": "ACCEPTED", "itemInspections": [{"returnItemId": item_id, "inspectionStatus": "ACCEPTED", "findings": "sealed"}], "creditsByItem": {item_id: 25}})
assert decision.status_code == 200, decision.text
wallet = client.get("/api/wallet", headers=customer_headers)
assert wallet.status_code == 200 and float(wallet.json()["availableBalance"]) == 25.0, wallet.text
duplicate = client.post(f"/api/staff/returns/{return_id}/decision", headers=staff_headers, json={"decision": "ACCEPTED", "itemInspections": [{"returnItemId": item_id, "inspectionStatus": "ACCEPTED"}], "creditsByItem": {item_id: 25}})
assert duplicate.status_code == 409, duplicate.text
print("PASS: registration, wallet, address, return creation, physical intake, all-or-nothing inspection, explicit credit award and duplicate-award prevention")
