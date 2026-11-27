"""Read-only snapshot of the deployed MediCycle MySQL/TiDB schema.

This script reads database metadata only. It does not query application rows,
execute DDL, create/alter/drop tables, or modify data.

Run from the repository root after configuring DB_USER, DB_PASSWORD, DB_HOST,
DB_PORT, and DB_NAME in .env (or the process environment).
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL
from dotenv import load_dotenv
import os


def build_engine():
    load_dotenv()
    required = ("DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise SystemExit(
            "Missing database configuration: " + ", ".join(missing)
            + ". Configure the existing .env file; do not paste credentials into chat."
        )

    url = URL.create(
        drivername="mysql+pymysql",
        username=os.environ["DB_USER"].strip(),
        password=os.environ["DB_PASSWORD"],
        host=os.getenv("DB_HOST", "localhost").strip(),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.environ["DB_NAME"].strip(),
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, echo=False)


def snapshot_schema(engine) -> dict:
    inspector = inspect(engine)
    table_names = sorted(inspector.get_table_names())
    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_name": engine.url.database,
        "server_dialect": engine.dialect.name,
        "table_count": len(table_names),
        "tables": {},
    }

    for table_name in table_names:
        columns = inspector.get_columns(table_name)
        result["tables"][table_name] = {
            "columns": [
                {
                    "name": col["name"],
                    "type": str(col["type"]),
                    "nullable": col.get("nullable"),
                    "default": str(col.get("default")) if col.get("default") is not None else None,
                    "autoincrement": col.get("autoincrement"),
                }
                for col in columns
            ],
            "primary_key": inspector.get_pk_constraint(table_name),
            "foreign_keys": inspector.get_foreign_keys(table_name),
            "unique_constraints": inspector.get_unique_constraints(table_name),
            "indexes": inspector.get_indexes(table_name),
        }

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="live_schema_snapshot.json",
        help="Output JSON path (default: live_schema_snapshot.json)",
    )
    args = parser.parse_args()

    engine = build_engine()
    try:
        snapshot = snapshot_schema(engine)
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(snapshot, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        column_count = sum(
            len(table["columns"]) for table in snapshot["tables"].values()
        )
        fk_count = sum(
            len(table["foreign_keys"]) for table in snapshot["tables"].values()
        )
        print("Read-only schema inspection completed.")
        print(f"Database: {snapshot['database_name']}")
        print(f"Tables: {snapshot['table_count']}")
        print(f"Columns: {column_count}")
        print(f"Foreign keys: {fk_count}")
        print(f"Snapshot: {output_path.resolve()}")
        print("No application rows were read and no database changes were made.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
