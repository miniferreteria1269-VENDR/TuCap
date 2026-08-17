from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.dependencies import require_tenant_id
from app.models import Tenant, TenantIdentifier, User
from app.services import auth
from app.services.auth import bootstrap_pilot_user, hash_password, verify_password
from app.services.tenants import provision_tenant
from app.database import Base


TEST_SECRET = "test-secret-that-is-longer-than-thirty-two-characters"


def test_passwords_are_hashed_and_verified() -> None:
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(jwt_secret=TEST_SECRET, jwt_expire_minutes=30),
    )
    user = User(
        id="user-1",
        tenant_id="tenant-1",
        email="owner@example.com",
        email_normalized="owner@example.com",
        full_name="Owner",
        password_hash="unused",
    )
    token = auth.create_access_token(user)
    assert auth.decode_access_token(token) == "user-1"


def test_expired_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        auth,
        "get_settings",
        lambda: SimpleNamespace(jwt_secret=TEST_SECRET, jwt_expire_minutes=30),
    )
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "user-1", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1), "iss": auth.ISSUER},
        TEST_SECRET,
        algorithm=auth.ALGORITHM,
    )
    with pytest.raises(HTTPException) as error:
        auth.decode_access_token(token)
    assert error.value.status_code == 401


def test_tenant_is_derived_from_user_after_disclaimer() -> None:
    user = User(
        tenant_id="tenant-1",
        email="owner@example.com",
        email_normalized="owner@example.com",
        full_name="Owner",
        password_hash="unused",
        disclaimer_accepted_at=datetime.now(timezone.utc),
    )
    assert require_tenant_id(user) == "tenant-1"


def test_business_access_requires_disclaimer() -> None:
    user = User(
        tenant_id="tenant-1",
        email="owner@example.com",
        email_normalized="owner@example.com",
        full_name="Owner",
        password_hash="unused",
    )
    with pytest.raises(HTTPException) as error:
        require_tenant_id(user)
    assert error.value.status_code == 403


def test_existing_pilot_is_tenant_one_and_next_tenant_is_two() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        pilot = Tenant(id="tenant-1", name="Pilot")
        db.add(pilot)
        db.flush()
        db.add(TenantIdentifier(tenant_id=pilot.id, tenant_number=1))
        db.flush()

        second = provision_tenant(db, "Second tenant")
        second_identifier = db.get(TenantIdentifier, second.id)

        assert db.get(TenantIdentifier, pilot.id).tenant_number == 1
        assert second_identifier.tenant_number == 2


def test_bootstrap_user_attaches_to_existing_pilot(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    settings = SimpleNamespace(
        bootstrap_tenant_id="tenant-1",
        bootstrap_admin_email="Owner@Example.com",
        bootstrap_admin_password="a-strong-test-password",
        bootstrap_admin_name="Pilot Owner",
    )
    monkeypatch.setattr(auth, "get_settings", lambda: settings)

    with Session(engine) as db:
        db.add(Tenant(id="tenant-1", name="Pilot"))
        db.flush()
        bootstrap_pilot_user(db)
        bootstrap_pilot_user(db)
        db.flush()

        users = list(db.scalars(select(User)))
        assert len(users) == 1
        assert users[0].tenant_id == "tenant-1"
        assert users[0].email_normalized == "owner@example.com"
