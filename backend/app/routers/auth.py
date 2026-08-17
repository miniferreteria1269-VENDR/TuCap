from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import get_current_user
from ..models import User
from ..schemas import AuthUserRead, DisclaimerAcceptance, LoginRequest, LoginResponse
from ..services.auth import authenticate_user, create_access_token, tenant_number_for


router = APIRouter(prefix="/auth", tags=["authentication"])


def user_response(db: Session, user: User) -> AuthUserRead:
    return AuthUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_number=tenant_number_for(db, user.tenant_id),
        disclaimer_accepted_at=user.disclaimer_accepted_at,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )
    return LoginResponse(access_token=create_access_token(user), user=user_response(db, user))


@router.get("/me", response_model=AuthUserRead)
def current_user(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUserRead:
    return user_response(db, user)


@router.post("/accept-disclaimer", response_model=AuthUserRead)
def accept_disclaimer(
    payload: DisclaimerAcceptance,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUserRead:
    if not payload.accepted:
        raise HTTPException(status_code=422, detail="Disclaimer acceptance is required")
    if user.disclaimer_accepted_at is None:
        user.disclaimer_accepted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
    return user_response(db, user)
