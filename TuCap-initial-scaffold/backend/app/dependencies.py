from typing import Annotated

from fastapi import Header, HTTPException


def require_tenant_id(x_tenant_id: Annotated[str | None, Header()] = None) -> str:
    """Temporary tenant boundary until authenticated sessions are added."""
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    return x_tenant_id

