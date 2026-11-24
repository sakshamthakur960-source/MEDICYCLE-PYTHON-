from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select

import models
from tests.conftest import register, make_reward, ledger_balance


# ---------- catalogue ----------

def test_rewards_list_shows_available_rewards_regardless_of_status_case(client, db):
    """Seed data uses 'AVAILABLE'. The catalogue must list it (TiDB/utf8mb4_bin compares case-sensitively)."""
    headers, _ = register(client)
    make_reward(db, "Upper", status="AVAILABLE")
    make_reward(db, "Lower", status="available")
    make_reward(db, "Hidden", status="INACTIVE")
    r = client.get("/api/rewards", headers=headers)
    assert r.status_code == 200
    titles = {x["title"] for x in r.json()}
    assert titles == {"Upper", "Lower"}


def test_rewards_list_hides_expired(client, db):
    headers, _ = register(client)
    make_reward(db, "Expired", valid_until=datetime.utcnow() - timedelta(days=1))
    make_reward(db, "Future", valid_until=datetime.utcnow() + timedelta(days=1))
    titles = {x["title"] for x in client.get("/api/rewards", headers=headers).json()}
    assert titles == {"Future"}


# ---------- welcome bonus (precondition for redemption) ----------

def test_registration_creates_100_credit_welcome_with_ledger(client, db):
    headers, user_id = register(client)
    w = client.get("/api/wallet", headers=headers).json()
    assert Decimal(str(w["availableBalance"])) == Decimal("100.00")
    wallet = db.scalar(select(models.Wallet))
    assert ledger_balance(db, wallet.walletId) == Decimal("100.00")


# ---------- redemption: success ----------

def test_redeem_success_debits_wallet_and_writes_ledger(client, db):
    headers, user_id = register(client)
    reward = make_reward(db, credits="60.00")
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert Decimal(str(body["remainingBalance"])) == Decimal("40.00")
    assert body["redemption"]["redemptionCode"].startswith("MC-")
    assert body["redemption"]["status"] == "ISSUED"

    wallet = db.scalar(select(models.Wallet))
    assert wallet.availableBalance == Decimal("40.00")
    debit = db.scalar(select(models.WalletTransaction).where(models.WalletTransaction.transactionType == "DEBIT"))
    assert debit is not None
    assert debit.amount == Decimal("60.00")
    assert str(debit.redemptionId).replace("-", "") == body["redemption"]["redemptionId"].replace("-", "")
    assert ledger_balance(db, wallet.walletId) == wallet.availableBalance


def test_redeem_exact_balance_leaves_zero(client, db):
    headers, _ = register(client)
    reward = make_reward(db, credits="100.00")
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    assert r.status_code == 201, r.text
    assert db.scalar(select(models.Wallet)).availableBalance == Decimal("0.00")


# ---------- redemption: rejections must not change anything ----------

def _snapshot(db):
    wallet = db.scalar(select(models.Wallet))
    db.refresh(wallet)
    n_tx = len(db.scalars(select(models.WalletTransaction)).all())
    n_red = len(db.scalars(select(models.RewardRedemption)).all())
    return wallet.availableBalance, n_tx, n_red


def test_insufficient_balance_rejected_and_nothing_changes(client, db):
    headers, _ = register(client)
    reward = make_reward(db, credits="500.00")
    before = _snapshot(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    assert r.status_code in (400, 409)
    assert "insufficient" in r.json()["detail"].lower()
    assert _snapshot(db) == before


def test_unknown_reward_404_and_nothing_changes(client, db):
    headers, _ = register(client)
    before = _snapshot(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(uuid4())}, headers=headers)
    assert r.status_code == 404
    assert _snapshot(db) == before


def test_expired_reward_rejected(client, db):
    headers, _ = register(client)
    reward = make_reward(db, valid_until=datetime.utcnow() - timedelta(hours=1))
    before = _snapshot(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    assert r.status_code == 409
    assert _snapshot(db) == before


def test_inactive_reward_rejected(client, db):
    headers, _ = register(client)
    reward = make_reward(db, status="INACTIVE")
    before = _snapshot(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    assert r.status_code == 409
    assert _snapshot(db) == before


def test_frozen_wallet_rejected(client, db):
    headers, _ = register(client)
    reward = make_reward(db)
    w = db.scalar(select(models.Wallet))
    w.walletStatus = "suspended"
    db.commit()
    before = _snapshot(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    assert r.status_code == 409
    assert _snapshot(db) == before


# ---------- auth / validation ----------

def test_requires_authentication(client, db):
    reward = make_reward(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)})
    assert r.status_code == 401


def test_bad_token_rejected(client, db):
    reward = make_reward(db)
    r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)},
                    headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_invalid_payload_422(client, db):
    headers, _ = register(client)
    assert client.post("/api/reward-redemptions", json={}, headers=headers).status_code == 422
    assert client.post("/api/reward-redemptions", json={"rewardId": "abc"}, headers=headers).status_code == 422


def test_user_cannot_spend_another_users_wallet(client, db):
    h1, _ = register(client, "a@example.com")
    h2, _ = register(client, "b@example.com")
    reward = make_reward(db, credits="60.00")
    assert client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=h1).status_code == 201
    wallets = {str(w.userId): w for w in db.scalars(select(models.Wallet)).all()}
    balances = sorted(w.availableBalance for w in wallets.values())
    assert balances == [Decimal("40.00"), Decimal("100.00")]


# ---------- repeated requests and ledger consistency ----------

def test_repeated_redemptions_stop_when_balance_runs_out(client, db):
    headers, _ = register(client)
    reward = make_reward(db, credits="40.00")
    codes = []
    statuses = []
    for _ in range(3):
        r = client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
        statuses.append(r.status_code)
        if r.status_code == 201:
            codes.append(r.json()["redemption"]["redemptionCode"])
    assert statuses == [201, 201, 409]          # 100 -> 60 -> 20 -> insufficient
    assert len(set(codes)) == 2                 # distinct codes
    wallet = db.scalar(select(models.Wallet))
    assert wallet.availableBalance == Decimal("20.00")
    assert ledger_balance(db, wallet.walletId) == wallet.availableBalance


def test_transactions_endpoint_shows_debit(client, db):
    headers, _ = register(client)
    reward = make_reward(db, credits="30.00")
    client.post("/api/reward-redemptions", json={"rewardId": str(reward.rewardId)}, headers=headers)
    tx = client.get("/api/wallet/transactions", headers=headers).json()
    assert {t["transactionType"] for t in tx} == {"CREDIT", "DEBIT"}
