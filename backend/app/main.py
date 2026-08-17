from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Base, SessionLocal, engine
from .models import Tenant
from .routers import borrowers, capital, loans
from .schemas import HealthResponse


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(borrowers.router, prefix="/api")
app.include_router(capital.router, prefix="/api")
app.include_router(loans.router, prefix="/api")


@app.on_event("startup")
def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        if db.get(Tenant, settings.bootstrap_tenant_id) is None:
            db.add(Tenant(id=settings.bootstrap_tenant_id, name=settings.bootstrap_tenant_name))
            db.commit()


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)
