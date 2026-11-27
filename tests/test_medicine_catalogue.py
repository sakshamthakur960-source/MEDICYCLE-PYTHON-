"""Tests for the authenticated medicine catalogue API."""
from sqlalchemy import select

import models
from tests.conftest import register


def test_medicine_catalogue_returns_ordered_records(client, db):
    headers, _ = register(client)
    db.add_all([
        models.Medicine(name="Zinc", genericName="Zinc", strength="20 mg", dosageForm="Tablet"),
        models.Medicine(name="Aspirin", genericName="Acetylsalicylic acid", strength="75 mg", dosageForm="Tablet"),
    ])
    db.commit()

    response = client.get("/api/medicines/catalogue", headers=headers)

    assert response.status_code == 200
    records = response.json()
    assert [item["name"] for item in records] == ["Aspirin", "Zinc"]
    assert all(item.get("medicineId") for item in records)


def test_medicine_catalogue_requires_authentication(client):
    response = client.get("/api/medicines/catalogue")
    assert response.status_code == 401
