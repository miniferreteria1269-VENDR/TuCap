from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..dependencies import CurrentSession, get_current_session
from ..models import AuthSession, User
from ..schemas import AuthUserRead, DisclaimerAcceptance, LoginRequest, LoginResponse
from ..services.auth import authenticate_user, create_access_token, create_auth_session, tenant_number_for


router = APIRouter(prefix="/auth", tags=["authentication"])


def user_response(db: Session, user: User, session: AuthSession) -> AuthUserRead:
    return AuthUserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        tenant_number=tenant_number_for(db, user.tenant_id),
        disclaimer_accepted_at=user.disclaimer_accepted_at,
        disclaimer_required=session.disclaimer_acknowledged_at is None,
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contraseña incorrectos",
        )
    session = create_auth_session(db, user)
    db.commit()
    return LoginResponse(access_token=create_access_token(user, session), user=user_response(db, user, session))


@router.get("/me", response_model=AuthUserRead)
def current_user(
    current: Annotated[CurrentSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUserRead:
    return user_response(db, current.user, current.session)


@router.post("/accept-disclaimer", response_model=AuthUserRead)
def accept_disclaimer(
    payload: DisclaimerAcceptance,
    current: Annotated[CurrentSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> AuthUserRead:
    if not payload.accepted:
        raise HTTPException(status_code=422, detail="Disclaimer acceptance is required")
    now = datetime.now(timezone.utc)
    current.session.disclaimer_acknowledged_at = now
    if current.user.disclaimer_accepted_at is None:
        current.user.disclaimer_accepted_at = now
    db.commit()
    return user_response(db, current.user, current.session)


@router.post("/logout")
def logout(
    current: Annotated[CurrentSession, Depends(get_current_session)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, bool]:
    current.session.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return {"logged_out": True}
