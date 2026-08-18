from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.database import Base
from app.dependencies import CurrentSession
from app.models import AuthSession, Tenant, TenantIdentifier, User
from app.routers import admin
from app.schemas import TenantProvisionCreate
from app.services.auth import hash_password, verify_password


def make_database() -> tuple[Session, Tenant, User, AuthSession]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    pilot = Tenant(id="tenant-1", name="Pilot")
    db.add(pilot)
    db.flush()
    db.add(TenantIdentifier(tenant_id=pilot.id, tenant_number=1))
    operator = User(
        tenant_id=pilot.id,
        email="owner@example.com",
        email_normalized="owner@example.com",
        full_name="Owner",
        password_hash=hash_password("operator-password"),
    )
    db.add(operator)
    db.flush()
    session = AuthSession(
        user_id=operator.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    db.add(session)
    db.commit()
    return db, pilot, operator, session


def platform_settings() -> SimpleNamespace:
    return SimpleNamespace(
        bootstrap_tenant_id="tenant-1",
        bootstrap_admin_email="Owner@Example.com",
    )


def test_bootstrap_operator_can_provision_tenant_two(monkeypatch: pytest.MonkeyPatch) -> None:
    db, _, operator, _ = make_database()
    monkeypatch.setattr(admin, "get_settings", platform_settings)
    try:
        authorized = admin.require_platform_admin(
            CurrentSession(user=operator, session=AuthSession(user_id=operator.id))
        )
        result = admin.provision_tenant_account(
            TenantProvisionCreate(
                tenant_name="Alfredo",
                admin_full_name="Alfredo Example",
                admin_email="Alfredo@Example.com",
                temporary_password="temporary-password",
            ),
            authorized,
            db,
        )

        assert result.tenant_number == 2
        assert result.tenant_name == "Alfredo"
        assert result.admin_email == "Alfredo@Example.com"
        tenant = db.get(Tenant, result.tenant_id)
        identifier = db.get(TenantIdentifier, result.tenant_id)
        user = db.get(User, result.user_id)
        assert tenant is not None
        assert identifier.tenant_number == 2
        assert user.tenant_id == tenant.id
        assert user.email_normalized == "alfredo@example.com"
        assert verify_password("temporary-password", user.password_hash)
        assert user.password_hash != "temporary-password"
    finally:
        db.close()


@pytest.mark.parametrize(
    ("tenant_id", "email"),
    [
        ("tenant-1", "someone-else@example.com"),
        ("tenant-2", "owner@example.com"),
    ],
)
def test_non_operator_cannot_provision_tenants(
    monkeypatch: pytest.MonkeyPatch,
    tenant_id: str,
    email: str,
) -> None:
    monkeypatch.setattr(admin, "get_settings", platform_settings)
    user = User(
        tenant_id=tenant_id,
        email=email,
        email_normalized=email.casefold(),
        full_name="Not operator",
        password_hash="unused",
    )
    with pytest.raises(HTTPException) as error:
        admin.require_platform_admin(
            CurrentSession(user=user, session=AuthSession(user_id="user-1"))
        )
    assert error.value.status_code == 403


def test_duplicate_email_does_not_create_an_extra_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    db, _, operator, _ = make_database()
    monkeypatch.setattr(admin, "get_settings", platform_settings)
    try:
        payload = TenantProvisionCreate(
            tenant_name="Duplicate",
            admin_full_name="Existing Owner",
            admin_email="OWNER@example.com",
            temporary_password="temporary-password",
        )
        with pytest.raises(HTTPException) as error:
            admin.provision_tenant_account(payload, operator, db)

        assert error.value.status_code == 409
        assert db.scalar(select(func.count(Tenant.id))) == 1
        assert db.scalar(select(func.count(TenantIdentifier.tenant_id))) == 1
        assert db.scalar(select(func.count(User.id))) == 1
    finally:
        db.close()
