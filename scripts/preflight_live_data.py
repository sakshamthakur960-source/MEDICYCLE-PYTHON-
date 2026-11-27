"""Read-only data-integrity preflight for MediCycle's MySQL-compatible TiDB schema.

Only SELECT statements are issued. The report contains aggregate counts and schema
identifiers, never row values or credentials. Metadata is read from information_schema
because SQLAlchemy's MySQL FK reflection is incompatible with some TiDB metadata rows.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


def database_url():
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


def quote(preparer, identifier):
    return preparer.quote(identifier)


def main():
    engine = create_engine(database_url(), pool_pre_ping=True, future=True)
    schema = os.getenv("DB_NAME")
    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "database_name": schema,
        "mode": "read_only_select_only",
        "checks": [],
        "tables": {},
        "summary": {},
    }
    failures = 0
    try:
        with engine.connect() as conn:
            preparer = engine.dialect.identifier_preparer
            tables = [
                row[0] for row in conn.execute(
                    text("SELECT TABLE_NAME FROM information_schema.TABLES "
                         "WHERE TABLE_SCHEMA = :schema AND TABLE_TYPE = 'BASE TABLE' "
                         "ORDER BY TABLE_NAME"),
                    {"schema": schema},
                )
            ]

            fk_rows = conn.execute(
                text("""
                    SELECT TABLE_NAME, CONSTRAINT_NAME, COLUMN_NAME,
                           REFERENCED_TABLE_NAME, REFERENCED_COLUMN_NAME, ORDINAL_POSITION
                    FROM information_schema.KEY_COLUMN_USAGE
                    WHERE TABLE_SCHEMA = :schema
                      AND REFERENCED_TABLE_NAME IS NOT NULL
                    ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION
                """),
                {"schema": schema},
            ).mappings().all()
            fk_groups = {}
            for row in fk_rows:
                key = (row["TABLE_NAME"], row["CONSTRAINT_NAME"])
                fk_groups.setdefault(key, []).append(row)

            unique_rows = conn.execute(
                text("""
                    SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, SEQ_IN_INDEX
                    FROM information_schema.STATISTICS
                    WHERE TABLE_SCHEMA = :schema AND NON_UNIQUE = 0
                    ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX
                """),
                {"schema": schema},
            ).mappings().all()
            unique_groups = {}
            for row in unique_rows:
                key = (row["TABLE_NAME"], row["INDEX_NAME"])
                unique_groups.setdefault(key, []).append(row["COLUMN_NAME"])

            for table in tables:
                qt = quote(preparer, table)
                count = int(conn.execute(text(f"SELECT COUNT(*) FROM {qt}")).scalar_one())
                report["tables"][table] = {"row_count": count}

                for (child_table, constraint), rows in fk_groups.items():
                    if child_table != table:
                        continue
                    local_cols = [r["COLUMN_NAME"] for r in rows]
                    remote_table = rows[0]["REFERENCED_TABLE_NAME"]
                    remote_cols = [r["REFERENCED_COLUMN_NAME"] for r in rows]
                    if not local_cols or not remote_table or any(c is None for c in remote_cols):
                        report["checks"].append({
                            "kind": "foreign_key_metadata",
                            "table": table,
                            "constraint": constraint,
                            "status": "REVIEW",
                        })
                        continue
                    join_terms = [
                        f"p.{quote(preparer, remote)} = c.{quote(preparer, local)}"
                        for local, remote in zip(local_cols, remote_cols)
                    ]
                    # MySQL composite FK rows are exempt when ANY child component is NULL.
                    all_nonnull = " AND ".join(
                        f"c.{quote(preparer, col)} IS NOT NULL" for col in local_cols
                    )
                    sql = (
                        f"SELECT COUNT(*) FROM {qt} AS c "
                        f"LEFT JOIN {quote(preparer, remote_table)} AS p "
                        f"ON {' AND '.join(join_terms)} "
                        f"WHERE ({all_nonnull}) "
                        f"AND p.{quote(preparer, remote_cols[0])} IS NULL"
                    )
                    orphan_count = int(conn.execute(text(sql)).scalar_one())
                    report["checks"].append({
                        "kind": "foreign_key_orphans",
                        "table": table,
                        "constraint": constraint,
                        "columns": local_cols,
                        "referenced_table": remote_table,
                        "orphan_count": orphan_count,
                        "status": "PASS" if orphan_count == 0 else "FAIL",
                    })
                    failures += orphan_count > 0

                for (unique_table, index_name), cols in unique_groups.items():
                    if unique_table != table or not cols:
                        continue
                    grouped = ", ".join(quote(preparer, col) for col in cols)
                    # NULL in any component exempts a row from MySQL unique-key collision.
                    nonnull = " AND ".join(
                        f"{quote(preparer, col)} IS NOT NULL" for col in cols
                    )
                    sql = (
                        f"SELECT COUNT(*) FROM (SELECT {grouped} FROM {qt} "
                        f"WHERE {nonnull} GROUP BY {grouped} "
                        f"HAVING COUNT(*) > 1) AS duplicate_groups"
                    )
                    duplicate_count = int(conn.execute(text(sql)).scalar_one())
                    report["checks"].append({
                        "kind": "unique_constraint_duplicates",
                        "table": table,
                        "constraint_or_index": index_name,
                        "columns": cols,
                        "duplicate_groups": duplicate_count,
                        "status": "PASS" if duplicate_count == 0 else "FAIL",
                    })
                    failures += duplicate_count > 0

            review_count = sum(c["status"] == "REVIEW" for c in report["checks"])
            failed_count = sum(c["status"] == "FAIL" for c in report["checks"])
            report["summary"] = {
                "table_count": len(tables),
                "check_count": len(report["checks"]),
                "failed_checks": failed_count,
                "review_checks": review_count,
                "result": "FAIL" if failures else "PASS_WITH_REVIEW" if review_count else "PASS",
            }
    except (SQLAlchemyError, RuntimeError, ValueError) as exc:
        diagnostic = {"exception_type": type(exc).__name__}
        if isinstance(exc, RuntimeError):
            diagnostic["reason"] = str(exc)
        elif isinstance(exc, ValueError):
            diagnostic["reason"] = "Invalid database configuration value (for example DB_PORT)."
        elif isinstance(exc, SQLAlchemyError):
            original = getattr(exc, "orig", None)
            args = getattr(original, "args", ()) if original is not None else ()
            if args and isinstance(args[0], int):
                diagnostic["driver_error_code"] = args[0]
            diagnostic["reason"] = "Database connection or read query failed; details redacted."
        report["error"] = diagnostic
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
