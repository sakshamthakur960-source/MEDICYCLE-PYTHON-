"""Read-only verification of MediCycle table creation."""
from sqlalchemy import inspect
from Database import engine
import models  # noqa: F401

inspector = inspect(engine)
tables = sorted(inspector.get_table_names())
print(f"Database tables found: {len(tables)}")
for table in tables:
    columns = inspector.get_columns(table)
    foreign_keys = inspector.get_foreign_keys(table)
    print(f"\n{table}: {len(columns)} columns, {len(foreign_keys)} foreign keys")
    for col in columns:
        nullable = "NULL" if col["nullable"] else "NOT NULL"
        print(f"  - {col['name']}: {col['type']} [{nullable}]")
