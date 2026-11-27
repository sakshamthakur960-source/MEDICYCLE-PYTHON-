"""Read-only data-integrity preflight for the live MediCycle MySQL/TiDB schema.

This script performs SELECT-only checks. It never issues DDL or DML and never
prints record values, credentials, or personal data. It reports aggregate counts.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import URL, create_engine, inspect, text
from sqlalchemy.exc import SQLAlchemyError


def database_url():
    # Load local .env when python-dotenv is installed; CI can use environment secrets.
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    except ImportError:
        pass

    required = ("DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
    return URL.create(
        "mysql+pymysql",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.environ["DB_NAME"],
        query={"charset": "utf8mb4"},
    )


def qname(preparer, name):
    return preparer.quote(name)


def main():
    engine = create_engine(database_url(), pool_pre_ping=True, future=True)
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_name": os.getenv("DB_NAME"),
        "mode": "read_only",
        "checks": [],
        "tables": {},
        "summary": {},
    }
    failures = 0
    try:
        with engine.connect() as conn:
            # MySQL/TiDB enforce read-only mode for the session transaction.
            conn.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            inspector = inspect(conn)
            preparer = engine.dialect.identifier_preparer
            tables = sorted(inspector.get_table_names())
            for table in tables:
                qt = qname(preparer, table)
                row_count = conn.execute(text(f"SELECT COUNT(*) FROM {qt}")).scalar_one()
                report["tables"][table] = {"row_count": int(row_count)}

                for fk in inspector.get_foreign_keys(table):
                    local_cols = fk.get("constrained_columns") or []
                    remote_cols = fk.get("referred_columns") or []
                    remote_table = fk.get("referred_table")
                    if not local_cols or not remote_cols or not remote_table or len(local_cols) != len(remote_cols):
                        report["checks"].append({
                            "kind": "foreign_key_metadata",
                            "table": table,
                            "constraint": fk.get("name"),
                            "status": "REVIEW",
                            "detail": "Incomplete FK metadata; manual review required",
                        })
                        continue
                    conditions = []
                    nonnull = []
                    for local, remote in zip(local_cols, remote_cols):
                        ql, qr = qname(preparer, local), qname(preparer, remote)
                        conditions.append(f"p.{qr} = c.{ql}")
                        nonnull.append(f"c.{ql} IS NOT NULL")
                    join_on = " AND ".join(conditions)
                    any_nonnull = " OR ".join(nonnull)
                    sql = (
                        f"SELECT COUNT(*) FROM {qt} AS c "
                        f"LEFT JOIN {qname(preparer, remote_table)} AS p ON {join_on} "
                        f"WHERE ({any_nonnull}) AND p.{qname(preparer, remote_cols[0])} IS NULL"
                    )
                    orphan_count = int(conn.execute(text(sql)).scalar_one())
                    check = {
                        "kind": "foreign_key_orphans",
                        "table": table,
                        "constraint": fk.get("name"),
                        "columns": local_cols,
                        "referenced_table": remote_table,
                        "orphan_count": orphan_count,
                        "status": "PASS" if orphan_count == 0 else "FAIL",
                    }
                    report["checks"].append(check)
                    failures += orphan_count > 0

                # Check all declared unique constraints and unique indexes for duplicates.
                unique_groups = []
                for uq in inspector.get_unique_constraints(table):
                    cols = uq.get("column_names") or []
                    if cols:
                        unique_groups.append((uq.get("name"), cols))
                for idx in inspector.get_indexes(table):
                    cols = idx.get("column_names") or []
                    if idx.get("unique") and cols and (idx.get("name"), cols) not in unique_groups:
                        unique_groups.append((idx.get("name"), cols))
                for name, cols in unique_groups:
                    grouped_cols = ", ".join(qname(preparer, c) for c in cols)
                    nonnull_filter = " AND ".join(
                        f"{qname(preparer, col)} IS NOT NULL" for col in cols
                    )
                    sql = (
                        f"SELECT COUNT(*) FROM (SELECT {grouped_cols} FROM {qt} "
                        f"WHERE {nonnull_filter} GROUP BY {grouped_cols} "
                        f"HAVING COUNT(*) > 1) AS duplicate_groups"
                    )
                    duplicate_groups = int(conn.execute(text(sql)).scalar_one())
                    report["checks"].append({
                        "kind": "unique_constraint_duplicates",
                        "table": table,
                        "constraint_or_index": name,
                        "columns": cols,
                        "duplicate_groups": duplicate_groups,
                        "status": "PASS" if duplicate_groups == 0 else "FAIL",
                    })
                    failures += duplicate_groups > 0

            report["summary"] = {
                "table_count": len(tables),
                "check_count": len(report["checks"]),
                "failed_checks": sum(1 for c in report["checks"] if c["status"] == "FAIL"),
                "review_checks": sum(1 for c in report["checks"] if c["status"] == "REVIEW"),
                "result": "FAIL" if failures else "PASS_WITH_REVIEW" if any(
                    c["status"] == "REVIEW" for c in report["checks"]
                ) else "PASS",
            }
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        # Error text is intentionally not serialized; drivers can include connection details.
        report["error"] = f"{type(exc).__name__}: preflight could not complete; inspect secured runner logs."
        report["summary"] = {"result": "ERROR"}
        failures += 1
    finally:
        engine.dispose()

    output = Path(os.getenv("PREFLIGHT_OUTPUT", "live_data_preflight.json"))
    output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    print(f"Aggregate report written to: {output}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
