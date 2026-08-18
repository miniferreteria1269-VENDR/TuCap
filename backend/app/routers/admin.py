from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_db
from ..dependencies import CurrentSession, get_current_session
from ..models import TenantIdentifier, User
from ..schemas import TenantProvisionCreate, TenantProvisionRead
from ..services.auth import hash_password, normalize_email
from ..services.tenants import provision_tenant


router = APIRouter(prefix="/admin", tags=["platform administration"])


def require_platform_admin(
    current: Annotated[CurrentSession, Depends(get_current_session)],
) -> User:
    settings = get_settings()
    configured_email = settings.bootstrap_admin_email
    if (
        configured_email is None
        or current.user.tenant_id != settings.bootstrap_tenant_id
        or normalize_email(current.user.email) != normalize_email(configured_email)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    return current.user


@router.post("/tenants", response_model=TenantProvisionRead, status_code=status.HTTP_201_CREATED)
def provision_tenant_account(
    payload: TenantProvisionCreate,
    _: Annotated[User, Depends(require_platform_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> TenantProvisionRead:
    tenant_name = payload.tenant_name.strip()
    admin_full_name = payload.admin_full_name.strip()
    admin_email = payload.admin_email.strip()
    if not tenant_name or not admin_full_name or not admin_email:
        raise HTTPException(status_code=422, detail="Tenant name, administrator name, and email are required")

    normalized_email = normalize_email(admin_email)
    existing = db.scalar(select(User).where(User.email_normalized == normalized_email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="A user with this email already exists")

    tenant = provision_tenant(db, tenant_name)
    user = User(
        tenant_id=tenant.id,
        email=admin_email,
        email_normalized=normalized_email,
        full_name=admin_full_name,
        password_hash=hash_password(payload.temporary_password),
    )
    db.add(user)
    db.flush()
    identifier = db.get(TenantIdentifier, tenant.id)
    db.commit()

    return TenantProvisionRead(
        tenant_id=tenant.id,
        tenant_number=identifier.tenant_number,
        tenant_name=tenant.name,
        user_id=user.id,
        admin_full_name=user.full_name,
        admin_email=user.email,
    )
