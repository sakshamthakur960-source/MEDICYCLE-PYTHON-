"""Isolated test harness: in-memory SQLite, no connection to TiDB/MySQL.

Environment variables are set BEFORE importing the app so that Database.py and
api/security.py import cleanly. The mysql+pymysql engine in Database.py is never
connected to; get_db is overridden to use SQLite.
"""
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Assigned (not setdefault) so a developer's real .env / shell variables, e.g. the
# TiDB host, can never be picked up by the test run. python-dotenv does not
# override variables that are already set.
os.environ["DB_USER"] = "test"
os.environ["DB_PASSWORD"] = "test"
os.environ["DB_HOST"] = "localhost"
os.environ["DB_PORT"] = "3306"
os.environ["DB_NAME"] = "medicycle"
os.environ["JWT_SECRET"] = "unit-test-secret-not-for-production-use-0123456789"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from Database import Base
import models
from api.main import app
from api.dependencies import get_db


@pytest.fixture()
def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def db(session_factory):
    s = session_factory()
    yield s
    s.close()


def register(client, email="customer@example.com", password="Password123!"):
    r = client.post("/api/auth/register", json={
        "fullName": "Test Customer", "email": email, "password": password})
    assert r.status_code == 201, r.text
    body = r.json()
    return {"Authorization": f"Bearer {body['accessToken']}"}, body["user"]["userId"]


def make_reward(db, title="Test Reward", credits="50.00", status="AVAILABLE", valid_until=None):
    reward = models.Reward(
        partnerName="Test Partner", title=title, description="test",
        creditsRequired=Decimal(credits), status=status, validUntil=valid_until)
    db.add(reward)
    db.commit()
    return reward


def ledger_balance(db, wallet_id):
    """Balance implied by the ledger: sum(CREDIT) - sum(DEBIT)."""
    rows = db.scalars(select(models.WalletTransaction).where(
        models.WalletTransaction.walletId == wallet_id)).all()
    total = Decimal("0")
    for t in rows:
        total += t.amount if t.transactionType == "CREDIT" else -t.amount
    return total
