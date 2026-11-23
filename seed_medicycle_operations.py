"""Seed MediCycle operational test data using the existing schema.

SAFE DEFAULT: dry-run only. This script performs INSERTs only. It never creates,
alters, updates, deletes, truncates, or drops database objects/rows.

Run from the backend project root:
    python seed_medicycle_operations.py
    python seed_medicycle_operations.py --apply --confirm "MEDICYCLE TEST DATA"

For a non-local database, additionally pass --allow-remote.
The generated credentials file is local and must never be committed.
"""
from __future__ import annotations

import argparse
import secrets
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from Database import engine
import models
from api.security import hash_password


CONFIRM_PHRASE = "MEDICYCLE TEST DATA"
PREFIX = "medicycle.opsdemo."
FACILITY_NAME = "MediCycle OPS TEST ONLY Facility - DO NOT VISIT"
CREDENTIALS_FILE = "medicycle_ops_test_credentials.txt"

ACCOUNTS = [
    ("customer", "MediCycle Operations Test Customer",
     f"{PREFIX}customer@example.com", "OPS-DEMO-CUSTOMER-001"),
    ("staff", "MediCycle Operations Test Staff",
     f"{PREFIX}staff@example.com", "OPS-DEMO-STAFF-001"),
    ("driver", "MediCycle Operations Test Driver",
     f"{PREFIX}driver@example.com", "OPS-DEMO-DRIVER-001"),
]

REQUIRED_TABLES = {
    "user", "userAddress", "medicine", "medicineBatch", "returnRequest",
    "returnItem", "pickupSlot", "pickupAssignment", "returnStatusHistory",
    "wallet", "walletTransaction", "facility", "facilityStaff", "driver",
    "vehicle", "trackingLog", "facilityIntake", "reward", "rewardRedemption",
}


def validate_target(allow_remote: bool) -> None:
    database = (engine.url.database or "").lower()
    host = (engine.url.host or "").lower()
    if database != "medicycle":
        raise RuntimeError(
            f"Safety stop: connected database is {database!r}; expected 'medicycle'."
        )
    if host not in {"localhost", "127.0.0.1", "::1"} and not allow_remote:
        raise RuntimeError(
            "Safety stop: this is a remote database. Re-run with --allow-remote "
            "only after confirming it is your intended test database."
        )
    existing = set(inspect(engine).get_table_names())
    missing = sorted(REQUIRED_TABLES - existing)
    if missing:
        raise RuntimeError("Safety stop: required existing tables are missing: "
                           + ", ".join(missing))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="Actually insert the test rows. Without this, changes roll back.")
    parser.add_argument("--allow-remote", action="store_true",
                        help="Permit a non-local database host; use only for a test database.")
    parser.add_argument("--confirm", default="",
                        help=f"Required with --apply: {CONFIRM_PHRASE!r}")
    args = parser.parse_args()

    if args.apply and args.confirm != CONFIRM_PHRASE:
        raise SystemExit(
            f"Safety stop. To insert rows, include --confirm \"{CONFIRM_PHRASE}\"."
        )

    validate_target(args.allow_remote)
    print(f"Target: {engine.url.host}:{engine.url.port or 3306}/{engine.url.database}")
    print("Schema check passed. INSERT statements only; no DDL, UPDATE, or DELETE.")

    now = datetime.utcnow()
    today = date.today()
    passwords = {key: secrets.token_urlsafe(20) for key, *_ in ACCOUNTS}
    created = {}

    with Session(engine) as db:
        try:
            emails = [entry[2] for entry in ACCOUNTS]
            phones = [entry[3] for entry in ACCOUNTS]
            existing_users = list(db.scalars(
                select(models.User).where(
                    (models.User.email.in_(emails)) | (models.User.phone.in_(phones))
                )
            ).all())
            if existing_users:
                identifiers = ", ".join(
                    f"{u.email or '-'} / {u.phone or '-'}" for u in existing_users
                )
                raise RuntimeError(
                    "Safety stop: one or more reserved operations-test accounts already "
                    f"exist ({identifiers}). Nothing was changed; this script does not "
                    "reset accounts or reuse existing records."
                )

            existing_facility = db.scalar(
                select(models.Facility).where(models.Facility.facilityName == FACILITY_NAME)
            )
            if existing_facility:
                raise RuntimeError("Safety stop: reserved test facility already exists.")

            users = {}
            for key, full_name, email, phone in ACCOUNTS:
                user = models.User(
                    fullName=full_name,
                    email=email,
                    phone=phone,
                    passwordHash=hash_password(passwords[key]),
                    accountStatus="active",
                    emailVerified=False,
                    phoneVerified=False,
                    createdAt=now,
                )
                db.add(user)
                db.flush()
                users[key] = user

                welcome = Decimal("100.00") if key == "customer" else Decimal("0.00")
                wallet = models.Wallet(
                    userId=user.userId,
                    availableBalance=welcome,
                    walletStatus="active",
                    updatedAt=now,
                    createdAt=now,
                )
                db.add(wallet)
                db.flush()

                if welcome:
                    db.add(models.WalletTransaction(
                        walletId=wallet.walletId,
                        transactionType="CREDIT",
                        amount=welcome,
                        referenceCode="OPS-WELCOME-" + secrets.token_hex(8).upper(),
                        description="One-time 100 MediCredits operations-test welcome bonus",
                        createdAt=now,
                    ))
            created["User"] = len(users)
            created["Wallet"] = len(users)
            created["WalletTransaction"] = 1

            facility = models.Facility(
                facilityName=FACILITY_NAME,
                facilityType="DEMO_ONLY",
                address="SYNTHETIC TEST ADDRESS - DO NOT VISIT",
                authorizationStatus="DEMO_ONLY",
                operatingStatus="INACTIVE",
                contactPhone=None,
                contactEmail=f"{PREFIX}facility@example.com",
                createdAt=now,
            )
            db.add(facility)
            db.flush()

            staff = models.FacilityStaff(
                facilityId=facility.facilityId,
                userId=users["staff"].userId,
                staffRole="OPS_TEST_STAFF",
                employmentStatus="ACTIVE",
                joinedAt=now,
            )
            db.add(staff)

            driver = models.Driver(
                fullName="MediCycle Operations Test Driver",
                phone="OPS-TEST-DRIVER-PROFILE-001",
                verificationStatus="VERIFIED",
                availabilityStatus="AVAILABLE",
                userId=users["driver"].userId,
                licenseNumber="OPS-TEST-LICENSE-001",
                licenseExpiry=today + timedelta(days=365),
                createdAt=now,
            )
            db.add(driver)
            db.flush()

            vehicle = models.Vehicle(
                registrationNumber="OPS-TEST-VEHICLE-001",
                vehicleType="DEMO_ONLY",
                capacityKg=Decimal("100.00"),
                vehicleStatus="AVAILABLE",
                assignedDriverId=driver.driverId,
                createdAt=now,
            )
            db.add(vehicle)
            db.flush()

            address = models.UserAddress(
                userId=users["customer"].userId,
                addressLine="SYNTHETIC TEST ADDRESS - DO NOT VISIT",
                city="Solan",
                state="Himachal Pradesh",
                postalCode="000000",
                latitude=None,
                longitude=None,
                isDefault=True,
                addressLabel="Operations test address",
                landmark="Fictional test data",
                createdAt=now,
            )
            db.add(address)
            db.flush()

            medicine = models.Medicine(
                name="MediCycle Operations Test Medicine",
                genericName="Synthetic test item",
                manufacturer="MediCycle Test Catalogue",
                strength="Test only",
                dosageForm="Tablet",
                barcode="MC-OPS-TEST-MED-001",
                description="Synthetic catalogue record for software testing only; not for use.",
                medicineCategory="DEMO_ONLY",
                createdAt=now,
            )
            db.add(medicine)
            db.flush()

            batch = models.MedicineBatch(
                medicineId=medicine.medicineId,
                batchNumber="OPS-TEST-BATCH-001",
                manufacturedOn=today - timedelta(days=30),
                expiresOn=today + timedelta(days=365),
                createdAt=now,
            )
            db.add(batch)
            db.flush()

            slot_date = today + timedelta(days=2)
            slot_start = datetime.combine(slot_date, time(10, 0))
            slot_end = datetime.combine(slot_date, time(12, 0))
            slot = models.PickupSlot(
                facilityId=facility.facilityId,
                slotDate=slot_date,
                startTime=slot_start,
                endTime=slot_end,
                capacity=1,
                bookedCount=1,
                slotStatus="FULL",
                createdAt=now,
            )
            db.add(slot)
            db.flush()

            request = models.ReturnRequest(
                userId=users["customer"].userId,
                addressId=address.addressId,
                returnMethod="DOORSTEP_PICKUP",
                pickupSlotId=slot.pickupSlotId,
                status="SUBMITTED",
                createdAt=now,
                facilityId=facility.facilityId,
                requestNotes="SYNTHETIC OPERATIONS TEST RETURN - not a real medicine collection",
            )
            db.add(request)
            db.flush()

            item = models.ReturnItem(
                returnId=request.returnId,
                medicineId=medicine.medicineId,
                batchId=batch.batchId,
                quantity=1,
                packagingCondition="TEST_ONLY",
                inspectionStatus="PENDING",
                creditsAwarded=Decimal("0.00"),
            )
            db.add(item)
            db.flush()

            assignment = models.PickupAssignment(
                returnId=request.returnId,
                driverId=driver.driverId,
                vehicleId=vehicle.vehicleId,
                assignedAt=now,
                status="ASSIGNED",
                routeId=None,
            )
            db.add(assignment)

            db.add(models.ReturnStatusHistory(
                returnId=request.returnId,
                previousStatus=None,
                newStatus="SUBMITTED",
                changedBy=users["customer"].userId,
                changeReason="Synthetic operations-test return seeded for API testing",
                changedAt=now,
            ))

            created.update({
                "Facility": 1,
                "FacilityStaff": 1,
                "Driver": 1,
                "Vehicle": 1,
                "UserAddress": 1,
                "Medicine": 1,
                "MedicineBatch": 1,
                "PickupSlot": 1,
                "ReturnRequest": 1,
                "ReturnItem": 1,
                "PickupAssignment": 1,
                "ReturnStatusHistory": 1,
            })

            if not args.apply:
                print("\nDRY RUN: rolling back all inserts. No rows were added.")
                db.rollback()
            else:
                db.commit()
                print("\nInserted rows:")
                for table, count in created.items():
                    print(f"  {table}: {count}")
        except Exception:
            db.rollback()
            raise

    if not args.apply:
        print("\nTo insert into the intended test database, use:")
        print('  python seed_medicycle_operations.py --apply --confirm "MEDICYCLE TEST DATA"')
        if (engine.url.host or "").lower() not in {"localhost", "127.0.0.1", "::1"}:
            print("  Add --allow-remote only after confirming the remote database is a test database.")
        return

    lines = [
        "MEDICYCLE OPERATIONS TEST ACCOUNTS - SYNTHETIC DATA ONLY",
        "Do not share publicly. Rotate/delete these test accounts after testing.",
        "The facility, address, medicine, vehicle, and return are fictional test data.",
        "The facility is deliberately DEMO_ONLY and INACTIVE. Do not visit or deliver anything.",
        "",
    ]
    for key, full_name, email, phone in ACCOUNTS:
        lines.extend([
            f"{key.upper()} | {full_name}",
            f"Email: {email}",
            f"Phone/login identifier: {phone}",
            f"Password: {passwords[key]}",
            "",
        ])
    lines.extend([
        "Customer welcome balance: 100.00 MediCredits (with CREDIT ledger entry).",
        "Staff and driver wallets: 0.00.",
        "No rewards are created by this script.",
        "The return begins at SUBMITTED with one assigned driver and one vehicle.",
        "The pickup slot is marked FULL because this test return already occupies it.",
    ])
    output = Path(CREDENTIALS_FILE)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nCredentials saved locally to: {output.resolve()}")
    print("Do not commit this credentials file to GitHub.")


if __name__ == "__main__":
    main()
