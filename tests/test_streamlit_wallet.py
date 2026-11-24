"""End-to-end UI tests: real Streamlit page -> real FastAPI app -> isolated SQLite.

streamlit_app/app.py calls requests.request(...). Here that call is routed into the
FastAPI TestClient (which uses the in-memory SQLite override from conftest), so no
network and no TiDB/MySQL connection is involved.
"""
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

import models
from tests.conftest import register, make_reward, ledger_balance

APP = Path(__file__).resolve().parents[1] / "streamlit_app" / "app.py"


@pytest.fixture(autouse=True)
def route_requests_to_testclient(client, monkeypatch):
    import requests

    def fake_request(method, url, json=None, params=None, headers=None, timeout=None, **_):
        return client.request(method, urlparse(url).path, json=json, params=params, headers=headers)

    monkeypatch.setattr(requests, "request", fake_request)


def new_app(token=None):
    at = AppTest.from_file(str(APP), default_timeout=30)
    if token:
        at.session_state["token"] = token
        at.session_state["user"] = {"fullName": "Test Customer"}
    return at


def open_wallet(token):
    at = new_app(token)
    at.run()
    at.sidebar.radio[0].set_value("Wallet & rewards").run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def redeem_buttons(at):
    return [b for b in at.button if b.label == "Redeem reward"]


def token_of(headers):
    return headers["Authorization"].split()[1]


def test_wallet_page_lists_rewards_and_blocks_unaffordable_ones(client, db):
    headers, _ = register(client)
    make_reward(db, "Cheap", credits="60.00")
    make_reward(db, "Pricey", credits="250.00")
    at = open_wallet(token_of(headers))

    assert float(at.metric[0].value) == 100.0
    buttons = redeem_buttons(at)
    assert len(buttons) == 2
    assert buttons[0].disabled is False          # 60 <= 100
    assert buttons[1].disabled is True           # 250 > 100
    assert any("You need 150 more MediCredits" in c.value for c in at.caption)
    assert not at.error


def test_redeem_from_ui_updates_balance_ledger_and_shows_code(client, db):
    headers, _ = register(client)
    make_reward(db, "Cheap", credits="60.00")
    at = open_wallet(token_of(headers))

    redeem_buttons(at)[0].click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error
    assert len(at.success) == 1
    msg = at.success[0].value
    assert "Reward redeemed" in msg and "MC-" in msg
    # Page was reloaded: balance shown is the NEW balance, not the stale one.
    assert float(at.metric[0].value) == 40.0
    # The now-unaffordable reward is disabled.
    assert redeem_buttons(at)[0].disabled is True

    wallet = db.scalar(select(models.Wallet))
    db.refresh(wallet)
    assert wallet.availableBalance == Decimal("40.00")
    assert ledger_balance(db, wallet.walletId) == wallet.availableBalance
    debits = db.scalars(select(models.WalletTransaction).where(
        models.WalletTransaction.transactionType == "DEBIT")).all()
    assert len(debits) == 1 and debits[0].redemptionId is not None

    # Success notice is shown once, not on every later rerun.
    at.run()
    assert not at.success


def test_withdrawn_reward_simply_disappears_from_the_page(client, db):
    """A reward deactivated after the page was drawn is gone on the next rerun; no redemption happens."""
    headers, _ = register(client)
    reward = make_reward(db, "Soon gone", credits="60.00")
    at = open_wallet(token_of(headers))
    assert len(redeem_buttons(at)) == 1

    reward.status = "INACTIVE"
    db.add(reward)
    db.commit()

    redeem_buttons(at)[0].click().run()
    assert redeem_buttons(at) == []
    assert not at.exception
    wallet = db.scalar(select(models.Wallet))
    db.refresh(wallet)
    assert wallet.availableBalance == Decimal("100.00")
    assert db.scalars(select(models.RewardRedemption)).all() == []


def test_backend_rejection_shows_friendly_message_not_raw_http(client, db):
    """Reward is listed and affordable, but the API refuses (suspended wallet): show the API's message only."""
    headers, _ = register(client)
    make_reward(db, "Cheap", credits="60.00")
    wallet = db.scalar(select(models.Wallet))
    wallet.walletStatus = "suspended"
    db.commit()

    at = open_wallet(token_of(headers))
    assert not redeem_buttons(at)[0].disabled

    redeem_buttons(at)[0].click().run()
    assert len(at.error) == 1
    text = at.error[0].value
    assert text == "Wallet or reward is not available"
    assert "HTTP" not in text
    assert not any("Request URL" in m.value for m in at.markdown)
    assert not at.success
    db.refresh(wallet)
    assert wallet.availableBalance == Decimal("100.00")
    assert db.scalars(select(models.RewardRedemption)).all() == []


def test_expired_or_invalid_token_returns_to_sign_in(client, db):
    at = new_app(token="this-token-is-not-valid")
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "token" not in at.session_state or not at.session_state["token"]
    assert any("session has expired" in w.value for w in at.warning)
    assert not at.error


def test_wrong_password_shows_invalid_credentials_not_session_expired(client, db):
    register(client, "someone@example.com", "RightPass123!")
    at = new_app()
    at.run()
    at.text_input[0].input("someone@example.com")
    at.text_input[1].input("WrongPass123!")
    [b for b in at.button if "Sign in" in b.label][0].click().run()
    assert any("Invalid credentials" in e.value for e in at.error)
    assert not any("session has expired" in w.value for w in at.warning)
