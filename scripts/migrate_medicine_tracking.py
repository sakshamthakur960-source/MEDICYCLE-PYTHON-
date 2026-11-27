"""Safe, idempotent schema migration for My Medicines.

Preview by default. Apply only after taking a verified TiDB backup:
    python scripts/migrate_medicine_tracking.py
    python scripts/migrate_medicine_tracking.py --apply
"""
import argparse
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateTable
from Database import engine
from models import ReturnBucketItem

COLUMNS = {
    "sourcePlatform": "VARCHAR(40) NULL",
    "externalOrderId": "VARCHAR(255) NULL",
    "purchaseDate": "DATE NULL",
    "isDemo": "BOOLEAN NOT NULL DEFAULT 0",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply the migration (otherwise preview only)")
    args = parser.parse_args()
    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("userMedicine")}
    statements = [f"ALTER TABLE userMedicine ADD COLUMN {name} {ddl}"
                  for name, ddl in COLUMNS.items() if name not in existing]
    bucket_exists = inspector.has_table("returnBucketItem")
    if not args.apply:
        print("DRY RUN — no database changes made.")
        for statement in statements:
            print(statement + ";")
        if not bucket_exists:
            ddl = str(CreateTable(ReturnBucketItem.__table__).compile(dialect=engine.dialect))
            print(ddl + ";")
        else:
            print("returnBucketItem already exists.")
        print("Re-run with --apply only after a verified backup.")
        return
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
    ReturnBucketItem.__table__.create(engine, checkfirst=True)
    print("Migration applied. Existing inventory rows were preserved.")


if __name__ == "__main__":
    main()
