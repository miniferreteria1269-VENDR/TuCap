from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import TenantIdentifier, User


ALGORITHM = "HS256"
ISSUER = "tucap-api"
password_hash = PasswordHash.recommended()


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return password_hash.verify(password, hashed)


def require_jwt_secret() -> str:
    secret = get_settings().jwt_secret
    if secret is None or len(secret) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return secret


def create_access_token(user: User) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
        "iss": ISSUER,
    }
    return jwt.encode(payload, require_jwt_secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> str:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            require_jwt_secret(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["sub", "iat", "exp", "iss"]},
        )
    except (InvalidTokenError, ValueError):
        raise unauthorized from None
    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise unauthorized
    return user_id


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email_normalized == normalize_email(email)))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user


def tenant_number_for(db: Session, tenant_id: str) -> int:
    identifier = db.get(TenantIdentifier, tenant_id)
    if identifier is None:
        raise RuntimeError("Tenant is missing its public identifier")
    return identifier.tenant_number


def bootstrap_pilot_user(db: Session) -> None:
    settings = get_settings()
    if (settings.bootstrap_admin_email is None) != (settings.bootstrap_admin_password is None):
        raise RuntimeError("Both bootstrap admin email and password must be configured")
    if settings.bootstrap_admin_email is None or settings.bootstrap_admin_password is None:
        return
    if len(settings.bootstrap_admin_password) < 12:
        raise RuntimeError("Bootstrap admin password must contain at least 12 characters")

    normalized = normalize_email(settings.bootstrap_admin_email)
    existing = db.scalar(select(User).where(User.email_normalized == normalized))
    if existing is not None:
        if existing.tenant_id != settings.bootstrap_tenant_id:
            raise RuntimeError("Bootstrap admin email already belongs to another tenant")
        return

    db.add(
        User(
            tenant_id=settings.bootstrap_tenant_id,
            email=settings.bootstrap_admin_email.strip(),
            email_normalized=normalized,
            full_name=settings.bootstrap_admin_name.strip() or "Administrador",
            password_hash=hash_password(settings.bootstrap_admin_password),
        )
    )
