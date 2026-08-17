from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import Tenant


DEMO_TENANT_ID = "00000000-0000-0000-0000-000000000001"


def main() -> None:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        tenant = db.scalar(select(Tenant).where(Tenant.id == DEMO_TENANT_ID))
        if tenant is None:
            db.add(Tenant(id=DEMO_TENANT_ID, name="TuCap Demo"))
            db.commit()
            print(f"Created demo tenant: {DEMO_TENANT_ID}")
        else:
            print(f"Demo tenant already exists: {DEMO_TENANT_ID}")


if __name__ == "__main__":
    main()

