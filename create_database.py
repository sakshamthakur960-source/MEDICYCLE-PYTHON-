"""Create missing MediCycle tables. Does not drop or alter existing tables."""
from sqlalchemy import inspect
from Database import Base, engine
import models  # noqa: F401 - imports and registers all model classes

EXPECTED_TABLE_COUNT = 39
registered = sorted(Base.metadata.tables)

if len(registered) != EXPECTED_TABLE_COUNT:
    raise RuntimeError(
        f"Expected {EXPECTED_TABLE_COUNT} model tables, found {len(registered)}: {registered}"
    )

# Validate that the configured MySQL server is reachable before DDL.
with engine.connect() as connection:
    connection.exec_driver_sql("SELECT 1")

Base.metadata.create_all(bind=engine)

existing = set(inspect(engine).get_table_names())
missing = sorted(set(registered) - existing)
if missing:
    raise RuntimeError(f"Some tables were not created: {missing}")

print(f"Success: {len(registered)} MediCycle tables exist in the configured database.")
for name in registered:
    print(f"  [OK] {name}")
