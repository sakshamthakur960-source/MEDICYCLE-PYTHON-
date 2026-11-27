from datetime import date, timedelta

import models
from tests.conftest import register


def make_medicine(db, name="Test Paracetamol"):
    medicine = models.Medicine(name=name, strength="500 mg", dosageForm="Tablet")
    db.add(medicine)
    db.commit()
    db.refresh(medicine)
    return medicine


def test_expired_inventory_is_added_to_return_bucket_once(client, db):
    headers, user_id = register(client)
    medicine = make_medicine(db)
    response = client.post("/api/my-medicines", headers=headers, json={
        "medicineId": str(medicine.medicineId),
        "batchNumber": "BATCH-EXPIRED-1",
        "expiresOn": (date.today() - timedelta(days=1)).isoformat(),
        "quantity": 2,
        "packagingState": "SEALED",
        "sourcePlatform": "TATA_1MG",
        "purchaseDate": date.today().isoformat(),
    })
    assert response.status_code == 201, response.text

    inventory = client.get("/api/my-medicines", headers=headers)
    assert inventory.status_code == 200, inventory.text
    assert inventory.json()[0]["expiryStatus"] == "EXPIRED"

    first_bucket = client.get("/api/return-bucket", headers=headers)
    second_bucket = client.get("/api/return-bucket", headers=headers)
    assert first_bucket.status_code == 200
    assert len(first_bucket.json()) == 1
    assert second_bucket.json() == first_bucket.json()
    assert first_bucket.json()[0]["quantity"] == 2


def test_near_expiry_is_not_added_to_return_bucket(client, db):
    headers, _ = register(client, email="near-expiry@example.com")
    medicine = make_medicine(db, "Cetirizine")
    response = client.post("/api/my-medicines", headers=headers, json={
        "medicineId": str(medicine.medicineId),
        "batchNumber": "BATCH-SOON-1",
        "expiresOn": (date.today() + timedelta(days=10)).isoformat(),
        "quantity": 1,
        "packagingState": "INTACT",
        "sourcePlatform": "PHARMEASY",
    })
    assert response.status_code == 201, response.text
    inventory = client.get("/api/my-medicines", headers=headers).json()
    assert inventory[0]["expiryStatus"] == "NEAR_EXPIRY"
    assert client.get("/api/return-bucket", headers=headers).json() == []


def test_demo_medicines_are_per_customer_and_idempotent(client, db):
    headers, _ = register(client, email="demo-user@example.com")
    for name in ("Aspirin", "Ibuprofen", "Omeprazole"):
        make_medicine(db, name)
    first = client.post("/api/my-medicines/demo", headers=headers)
    second = client.post("/api/my-medicines/demo", headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["created"] == 3
    assert second.json()["created"] == 0
    records = client.get("/api/my-medicines", headers=headers).json()
    assert len(records) == 3
    assert all(item["isDemo"] for item in records)


def test_return_bucket_items_can_be_submitted_independently(client, db):
    headers, _ = register(client, email="independent-returns@example.com")
    first_medicine = make_medicine(db, "Expired Medicine A")
    second_medicine = make_medicine(db, "Expired Medicine B")

    for medicine, batch_number in (
        (first_medicine, "INDEPENDENT-EXPIRED-A"),
        (second_medicine, "INDEPENDENT-EXPIRED-B"),
    ):
        response = client.post("/api/my-medicines", headers=headers, json={
            "medicineId": str(medicine.medicineId),
            "batchNumber": batch_number,
            "expiresOn": (date.today() - timedelta(days=2)).isoformat(),
            "quantity": 1,
            "packagingState": "SEALED",
            "sourcePlatform": "TATA_1MG",
        })
        assert response.status_code == 201, response.text

    bucket = client.get("/api/return-bucket", headers=headers).json()
    assert len(bucket) == 2

    facility = models.Facility(
        facilityName="Test Authorized Facility",
        facilityType="COLLECTION",
        address="Test address",
        authorizationStatus="APPROVED",
        operatingStatus="OPERATIONAL",
    )
    db.add(facility)
    db.commit()
    db.refresh(facility)

    first_return = client.post("/api/return-bucket/submit", headers=headers, json={
        "bucketItemIds": [bucket[0]["bucketItemId"]],
        "returnMethod": "PHARMACY_DROPOFF",
        "facilityId": str(facility.facilityId),
    })
    assert first_return.status_code == 201, first_return.text
    assert first_return.json()["submittedItems"] == 1

    remaining = client.get("/api/return-bucket", headers=headers).json()
    assert len(remaining) == 1
    assert remaining[0]["bucketItemId"] == bucket[1]["bucketItemId"]

    second_return = client.post("/api/return-bucket/submit", headers=headers, json={
        "bucketItemIds": [bucket[1]["bucketItemId"]],
        "returnMethod": "PHARMACY_DROPOFF",
        "facilityId": str(facility.facilityId),
    })
    assert second_return.status_code == 201, second_return.text
    assert second_return.json()["submittedItems"] == 1
    assert client.get("/api/return-bucket", headers=headers).json() == []
