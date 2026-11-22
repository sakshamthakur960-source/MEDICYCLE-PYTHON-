"""Safely seed clearly-labelled MediCycle development/demo reference data.

- Targets only the configured `medicycle` database.
- Never creates, alters, or drops tables.
- Never deletes or updates existing rows.
- Uses natural-key checks so reruns add only missing records.
- Does not create customer/staff accounts or fake customer addresses.

Run from the project root:
    python seed_demo.py
    python seed_demo.py --dry-run
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from Database import engine
import models


DEMO_FACILITY_NAME = "MediCycle DEMO Facility - Not Operational"
DEMO_DRIVER_PHONE = "DEMO-DRIVER-001"  # deliberately not a telephone number
DEMO_VEHICLE_REGISTRATION = "DEMO-MC-VEHICLE-001"  # not a road registration

MEDICINES = [
    {
        "name": "Paracetamol 500 mg", "genericName": "Paracetamol",
        "manufacturer": "MediCycle Demo Catalogue", "strength": "500 mg",
        "dosageForm": "Tablet", "barcode": "MC-DEMO-PARA-500",
        "description": "Fictional catalogue record for software demonstration only.",
        "medicineCategory": "Analgesic",
        "batches": [("DEMO-PARA-A", date(2025, 1, 1), date(2027, 12, 31)),
                    ("DEMO-PARA-B", date(2025, 6, 1), date(2028, 5, 31))],
    },
    {
        "name": "Cetirizine 10 mg", "genericName": "Cetirizine Hydrochloride",
        "manufacturer": "MediCycle Demo Catalogue", "strength": "10 mg",
        "dosageForm": "Tablet", "barcode": "MC-DEMO-CET-10",
        "description": "Fictional catalogue record for software demonstration only.",
        "medicineCategory": "Antihistamine",
        "batches": [("DEMO-CET-A", date(2025, 1, 1), date(2027, 12, 31)),
                    ("DEMO-CET-B", date(2025, 6, 1), date(2028, 5, 31))],
    },
    {
        "name": "Amoxicillin 500 mg", "genericName": "Amoxicillin",
        "manufacturer": "MediCycle Demo Catalogue", "strength": "500 mg",
        "dosageForm": "Capsule", "barcode": "MC-DEMO-AMOX-500",
        "description": "Fictional catalogue record for software demonstration only.",
        "medicineCategory": "Antibiotic",
        "batches": [("DEMO-AMOX-A", date(2025, 1, 1), date(2027, 12, 31)),
                    ("DEMO-AMOX-B", date(2025, 6, 1), date(2028, 5, 31))],
    },
    {
        "name": "ORS Sachet 21 g", "genericName": "Oral Rehydration Salts",
        "manufacturer": "MediCycle Demo Catalogue", "strength": "21 g",
        "dosageForm": "Powder", "barcode": "MC-DEMO-ORS-21",
        "description": "Fictional catalogue record for software demonstration only.",
        "medicineCategory": "Rehydration",
        "batches": [("DEMO-ORS-A", date(2025, 1, 1), date(2027, 12, 31)),
                    ("DEMO-ORS-B", date(2025, 6, 1), date(2028, 5, 31))],
    },
    {
        "name": "Vitamin C 500 mg", "genericName": "Ascorbic Acid",
        "manufacturer": "MediCycle Demo Catalogue", "strength": "500 mg",
        "dosageForm": "Tablet", "barcode": "MC-DEMO-VITC-500",
        "description": "Fictional catalogue record for software demonstration only.",
        "medicineCategory": "Supplement",
        "batches": [("DEMO-VITC-A", date(2025, 1, 1), date(2027, 12, 31)),
                    ("DEMO-VITC-B", date(2025, 6, 1), date(2028, 5, 31))],
    },
]

# Only these tables are touched. All are existing entities in the supplied models.
SEEDED_MODELS = (
    models.Medicine, models.MedicineBatch, models.Facility,
    models.PickupSlot, models.Driver, models.Vehicle,
)


def validate_target_database() -> None:
    database_name = (engine.url.database or "").lower()
    if database_name != "medicycle":
        raise RuntimeError(
            f"Safety stop: configured database is {database_name!r}, not 'medicycle'. "
            "Check DB_NAME in .env. No data was changed."
        )

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = [m.__tablename__ for m in SEEDED_MODELS if m.__tablename__ not in existing_tables]
    if missing_tables:
        raise RuntimeError(
            "Safety stop: required existing tables are missing: " + ", ".join(missing_tables)
            + ". This seeder will not create or migrate tables. No data was changed."
        )

    schema_errors: list[str] = []
    for model in SEEDED_MODELS:
        actual_columns = {c["name"] for c in inspector.get_columns(model.__tablename__)}
        required_columns = {c.name for c in model.__table__.columns}
        missing_columns = sorted(required_columns - actual_columns)
        if missing_columns:
            schema_errors.append(f"{model.__tablename__}: {', '.join(missing_columns)}")
    if schema_errors:
        raise RuntimeError(
            "Safety stop: the existing database schema differs from the current models. "
            "Missing mapped columns: " + "; ".join(schema_errors)
            + ". No data was changed; reconcile the schema before seeding."
        )


def seed_reference_data(db: Session) -> dict[str, int]:
    added = {"Medicine": 0, "MedicineBatch": 0, "Facility": 0,
             "PickupSlot": 0, "Driver": 0, "Vehicle": 0}

    # 1. Catalogue and batches: Medicine -> MedicineBatch (one-to-many).
    for spec in MEDICINES:
        medicine = db.scalar(select(models.Medicine).where(models.Medicine.barcode == spec["barcode"]))
        if medicine is None:
            values = {k: v for k, v in spec.items() if k != "batches"}
            medicine = models.Medicine(**values)
            db.add(medicine)
            db.flush()
            added["Medicine"] += 1

        for batch_number, manufactured_on, expires_on in spec["batches"]:
            batch = db.scalar(
                select(models.MedicineBatch).where(
                    models.MedicineBatch.medicineId == medicine.medicineId,
                    models.MedicineBatch.batchNumber == batch_number,
                )
            )
            if batch is None:
                db.add(models.MedicineBatch(
                    medicineId=medicine.medicineId,
                    batchNumber=batch_number,
                    manufacturedOn=manufactured_on,
                    expiresOn=expires_on,
                ))
                added["MedicineBatch"] += 1

    # 2. A clearly non-operational facility is used only to anchor demo slots.
    # It is deliberately NOT marked approved/authorized or active.
    facility = db.scalar(
        select(models.Facility).where(models.Facility.facilityName == DEMO_FACILITY_NAME)
    )
    if facility is None:
        facility = models.Facility(
            facilityName=DEMO_FACILITY_NAME,
            facilityType="DEMO_ONLY",
            address="DEMO ONLY - not a real address; do not travel or deliver here",
            authorizationStatus="DEMO_ONLY",
            operatingStatus="INACTIVE",
            contactPhone=None,
            contactEmail=None,
        )
        db.add(facility)
        db.flush()
        added["Facility"] += 1

    # Slots are visible to the pickup-slot UI, but the linked facility is not
    # authorized or operational. These slots are for local demonstration only; the linked facility remains inactive and is not a real service location.
    today = date.today()
    for offset in range(1, 8):
        slot_day = today + timedelta(days=offset)
        start_at = datetime.combine(slot_day, time(10, 0))
        end_at = datetime.combine(slot_day, time(12, 0))
        exists = db.scalar(select(models.PickupSlot.pickupSlotId).where(
            models.PickupSlot.facilityId == facility.facilityId,
            models.PickupSlot.slotDate == slot_day,
            models.PickupSlot.startTime == start_at,
            models.PickupSlot.endTime == end_at,
        ))
        if exists is None:
            db.add(models.PickupSlot(
                facilityId=facility.facilityId,
                slotDate=slot_day,
                startTime=start_at,
                endTime=end_at,
                capacity=8,
                bookedCount=0,
                slotStatus="AVAILABLE",
            ))
            added["PickupSlot"] += 1

    # 3. Fictional driver and vehicle identifiers; no real phone/registration.
    driver = db.scalar(select(models.Driver).where(models.Driver.phone == DEMO_DRIVER_PHONE))
    if driver is None:
        driver = models.Driver(
            fullName="MediCycle Demo Courier",
            phone=DEMO_DRIVER_PHONE,
            verificationStatus="VERIFIED",
            availabilityStatus="AVAILABLE",
            licenseNumber="DEMO-LICENSE-001",
            licenseExpiry=None,
            userId=None,
        )
        db.add(driver)
        db.flush()
        added["Driver"] += 1

    vehicle = db.scalar(select(models.Vehicle).where(
        models.Vehicle.registrationNumber == DEMO_VEHICLE_REGISTRATION
    ))
    if vehicle is None:
        db.add(models.Vehicle(
            registrationNumber=DEMO_VEHICLE_REGISTRATION,
            vehicleType="DEMO_ONLY",
            capacityKg=Decimal("100.00"),
            vehicleStatus="AVAILABLE",
            assignedDriverId=driver.driverId,
        ))
        added["Vehicle"] += 1

    db.flush()
    return added


def main() -> int:
    parser = argparse.ArgumentParser(description="Safely add MediCycle demo reference data.")
    parser.add_argument("--dry-run", action="store_true", help="validate and count changes, then roll back")
    args = parser.parse_args()

    validate_target_database()
    print(f"Connected target: {engine.url.host}:{engine.url.port or 3306}/{engine.url.database}")
    print("Schema check: passed. No DDL (table creation/alteration) will be executed.")

    with Session(engine) as db:
        with db.begin():
            added = seed_reference_data(db)
            print("\nDemo seeding summary:")
            for table, count in added.items():
                print(f"  {table}: {count} new row(s)")
            if args.dry_run:
                print("\nDRY RUN: transaction will be rolled back; database remains unchanged.")
                db.rollback()
            else:
                print("\nAll inserts are in one transaction; committing now.")

    if not args.dry_run:
        print("\nSeed completed. Existing rows were not updated or deleted.")
        print("Important: facility/address and driver/vehicle identifiers are fictional. The facility is inactive; slots and driver/vehicle statuses are enabled only to exercise local demo workflows. Never use them for real collections or deliveries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
