from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .services.auth import decode_access_token


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_tenant_id(current_user: Annotated[User, Depends(get_current_user)]) -> str:
    """Derive the tenant boundary exclusively from the authenticated user."""
    if current_user.disclaimer_accepted_at is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Legal disclaimer acceptance is required",
        )
    return current_user.tenant_id
