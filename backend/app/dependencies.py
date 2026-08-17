from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import AuthSession, User
from .services.auth import decode_access_token, session_has_expired


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentSession:
    user: User
    session: AuthSession


def get_current_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> CurrentSession:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    claims = decode_access_token(credentials.credentials)
    user = db.get(User, claims.user_id)
    session = db.get(AuthSession, claims.session_id)
    if (
        user is None
        or not user.is_active
        or session is None
        or session.user_id != user.id
        or session_has_expired(session)
    ):
        if session is not None and session.revoked_at is None:
            session.revoked_at = datetime.now(timezone.utc)
            db.commit()
        raise unauthorized

    session.last_activity_at = datetime.now(timezone.utc)
    db.commit()
    return CurrentSession(user=user, session=session)


def get_current_user(current: Annotated[CurrentSession, Depends(get_current_session)]) -> User:
    return current.user


def require_tenant_id(current: Annotated[CurrentSession, Depends(get_current_session)]) -> str:
    """Derive the tenant boundary exclusively from the authenticated user."""
    if current.session.disclaimer_acknowledged_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Legal disclaimer acceptance is required",
        )
    return current.user.tenant_id
