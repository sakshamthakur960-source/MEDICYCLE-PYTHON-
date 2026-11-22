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

required = ("DB_USER", "DB_PASSWORD", "DB_NAME")
missing = [key for key in required if not os.getenv(key)]
if missing:
    raise RuntimeError(
        "Missing database configuration: " + ", ".join(missing) +
        ". Copy .env.example to .env and fill in the values."
    )

connection_url = URL.create(
    drivername="mysql+pymysql",
    username=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "medicycle"),
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
