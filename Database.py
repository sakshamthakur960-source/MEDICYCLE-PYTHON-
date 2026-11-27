"""
MediCycle database connection.
Credentials are loaded from environment variables / .env.
Never hard-code database passwords in this file.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

def _env_value(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()

required = ("DB_USER", "DB_PASSWORD", "DB_NAME")
missing = [key for key in required if not _env_value(key)]
if missing:
    raise RuntimeError(
        "Missing database configuration: " + ", ".join(missing) +
        ". Copy .env.example to .env and fill in the values."
    )

connection_url = URL.create(
    drivername="mysql+pymysql",
    username=_env_value("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=_env_value("DB_HOST", "localhost"),
    port=int(_env_value("DB_PORT", "3306")),
    database=_env_value("DB_NAME", "medicycle"),
    query={"charset": "utf8mb4"},
)

engine = create_engine(
    connection_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

class Base(DeclarativeBase):
    pass
