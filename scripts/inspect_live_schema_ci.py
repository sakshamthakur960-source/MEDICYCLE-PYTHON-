"""Read-only TiDB/MySQL schema snapshot for GitHub Actions."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import URL

required=("DB_USER","DB_PASSWORD","DB_NAME","DB_HOST")
missing=[k for k in required if not os.getenv(k)]
if missing:
    raise SystemExit("Missing required GitHub Actions secrets: "+", ".join(missing))
url=URL.create(
    "mysql+pymysql",
    username=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"],
    port=int(os.getenv("DB_PORT","4000")),
    database=os.environ["DB_NAME"],
    query={"charset":"utf8mb4"},
)
engine=create_engine(url,pool_pre_ping=True,connect_args={"connect_timeout":20,"ssl_verify_cert":True,"ssl_verify_identity":True})
try:
    inspector=inspect(engine)
    tables=sorted(inspector.get_table_names())
    snapshot={
      "generated_at_utc":datetime.now(timezone.utc).isoformat(),
      "database_name":engine.url.database,
      "dialect":engine.dialect.name,
      "table_count":len(tables),
      "tables":{}
    }
    for name in tables:
      snapshot["tables"][name]={
        "columns":[
          {"name":c["name"],"type":str(c["type"]),"nullable":c.get("nullable"),
           "default":str(c.get("default")) if c.get("default") is not None else None,
           "autoincrement":c.get("autoincrement")}
          for c in inspector.get_columns(name)
        ],
        "primary_key":inspector.get_pk_constraint(name),
        "foreign_keys":inspector.get_foreign_keys(name),
        "unique_constraints":inspector.get_unique_constraints(name),
        "indexes":inspector.get_indexes(name),
      }
    Path("live_schema_snapshot.json").write_text(json.dumps(snapshot,indent=2,default=str)+"\n",encoding="utf-8")
    print(f"Read-only schema snapshot complete: {len(tables)} tables; {sum(len(t['columns']) for t in snapshot['tables'].values())} columns.")
finally:
    engine.dispose()
