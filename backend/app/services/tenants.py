from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Tenant, TenantIdentifier


def provision_tenant(db: Session, name: str) -> Tenant:
    """Create an isolated tenant and assign the next human-facing number."""
    next_number = db.scalar(select(func.coalesce(func.max(TenantIdentifier.tenant_number), 0) + 1))
    tenant = Tenant(name=name)
    db.add(tenant)
    db.flush()
    db.add(TenantIdentifier(tenant_id=tenant.id, tenant_number=int(next_number)))
    db.flush()
    return tenant
