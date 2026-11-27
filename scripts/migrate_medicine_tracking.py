"""Validated, idempotent schema migration for My Medicines.

Preview by default. Apply only after taking and verifying a TiDB backup:
    python scripts/migrate_medicine_tracking.py
    python scripts/migrate_medicine_tracking.py --apply
"""
import argparse

from sqlalchemy import Boolean, Date, String, inspect, text
from sqlalchemy.schema import CreateTable

from Database import engine
from models import ReturnBucketItem

COLUMNS = {
    "sourcePlatform": {"ddl": "VARCHAR(40) NULL", "family": "string", "length": 40, "nullable": True},
    "externalOrderId": {"ddl": "VARCHAR(255) NULL", "family": "string", "length": 255, "nullable": True},
    "purchaseDate": {"ddl": "DATE NULL", "family": "date", "nullable": True},
    "isDemo": {"ddl": "BOOLEAN NOT NULL DEFAULT 0", "family": "boolean", "nullable": False},
}

BUCKET_COLUMNS = {
    "bucketItemId", "userId", "userMedicineId", "status", "createdAt", "submittedReturnId"
}
BUCKET_FOREIGN_KEYS = {
    ("userId", "user", "userId"),
    ("userMedicineId", "userMedicine", "userMedicineId"),
    ("submittedReturnId", "returnRequest", "returnId"),
}
BUCKET_COLUMN_TYPES = {
    "bucketItemId": ("char", 32, False),
    "userId": ("char", 32, False),
    "userMedicineId": ("char", 32, False),
    "status": ("string", 40, False),
    "createdAt": ("datetime", None, False),
    "submittedReturnId": ("char", 32, True),
}


def _type_matches(column_type, expected):
    family = expected["family"]
    if family == "string":
        return isinstance(column_type, String) and column_type.length == expected["length"]
    if family == "date":
        return isinstance(column_type, Date) and not getattr(column_type, "datetime", False)
    if family == "boolean":
        # TiDB/MySQL commonly reflects BOOLEAN as TINYINT(1).
        return column_type.__class__.__name__.lower() in {"boolean", "tinyint"}
    return False


def validate_user_medicine_columns(inspector):
    actual = {column["name"]: column for column in inspector.get_columns("userMedicine")}
    problems = []
    for name, expected in COLUMNS.items():
        column = actual.get(name)
        if column is None:
            continue
        if not _type_matches(column["type"], expected):
            problems.append(f"userMedicine.{name}: unexpected type {column['type']}")
        if column["nullable"] != expected["nullable"]:
            problems.append(f"userMedicine.{name}: nullable={column['nullable']}, expected {expected['nullable']}")
        if name == "isDemo" and column.get("default") is None:
            problems.append("userMedicine.isDemo: missing database default (expected false/0)")
    return problems


def validate_bucket_table(inspector):
    if not inspector.has_table("returnBucketItem"):
        return []
    problems = []
    columns = {column["name"] for column in inspector.get_columns("returnBucketItem")}
    missing = BUCKET_COLUMNS - columns
    if missing:
        problems.append("returnBucketItem missing columns: " + ", ".join(sorted(missing)))
    for column in inspector.get_columns("returnBucketItem"):
        name = column["name"]
        expected = BUCKET_COLUMN_TYPES.get(name)
        if expected is None:
            continue
        family, length, nullable = expected
        actual_type = column["type"]
        type_name = actual_type.__class__.__name__.lower()
        if family == "char" and not (type_name in {"char", "varchar"} and actual_type.length == length):
            problems.append(f"returnBucketItem.{name}: unexpected type {actual_type}")
        elif family == "string" and not (isinstance(actual_type, String) and actual_type.length == length):
            problems.append(f"returnBucketItem.{name}: unexpected type {actual_type}")
        elif family == "datetime" and type_name != "datetime":
            problems.append(f"returnBucketItem.{name}: unexpected type {actual_type}")
        if column["nullable"] != nullable:
            problems.append(f"returnBucketItem.{name}: nullable={column['nullable']}, expected {nullable}")

    pk = set(inspector.get_pk_constraint("returnBucketItem").get("constrained_columns") or [])
    if pk != {"bucketItemId"}:
        problems.append(f"returnBucketItem primary key is {sorted(pk)}, expected ['bucketItemId']")

    foreign_keys = set()
    for fk in inspector.get_foreign_keys("returnBucketItem"):
        local = fk.get("constrained_columns") or []
        remote = fk.get("referred_columns") or []
        if len(local) == 1 and len(remote) == 1:
            foreign_keys.add((local[0], fk.get("referred_table"), remote[0]))
    missing_fks = BUCKET_FOREIGN_KEYS - foreign_keys
    if missing_fks:
        problems.append("returnBucketItem missing foreign keys: " + repr(sorted(missing_fks)))

    unique_sets = {
        tuple(sorted(item.get("column_names") or []))
        for item in inspector.get_unique_constraints("returnBucketItem")
    }
    if ("userMedicineId",) not in unique_sets:
        problems.append("returnBucketItem missing unique constraint on userMedicineId")
    return problems


def validate_schema(inspector):
    problems = validate_user_medicine_columns(inspector)
    problems.extend(validate_bucket_table(inspector))
    if problems:
        raise RuntimeError("Schema validation failed:\n - " + "\n - ".join(problems))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply the migration (otherwise preview only)")
    args = parser.parse_args()

    inspector = inspect(engine)
    if not inspector.has_table("userMedicine"):
        raise RuntimeError("Required table userMedicine does not exist; refusing to migrate.")

    validate_schema(inspector)
    existing = {column["name"] for column in inspector.get_columns("userMedicine")}
    statements = [
        f"ALTER TABLE userMedicine ADD COLUMN {name} {definition['ddl']}"
        for name, definition in COLUMNS.items() if name not in existing
    ]
    bucket_exists = inspector.has_table("returnBucketItem")

    if not args.apply:
        print("DRY RUN — no database changes made.")
        for statement in statements:
            print(statement + ";")
        if not bucket_exists:
            ddl = str(CreateTable(ReturnBucketItem.__table__).compile(dialect=engine.dialect))
            print(ddl + ";")
        else:
            print("returnBucketItem exists and passed structural validation.")
        print("Re-run with --apply only after a verified backup.")
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        ReturnBucketItem.__table__.create(connection, checkfirst=True)

    validate_schema(inspect(engine))
    print("Migration applied and schema validation passed. Existing inventory and return rows were not deleted.")


if __name__ == "__main__":
    main()
