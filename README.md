# TuCap

TuCap is a phone-first capital and private-loan tracking application. It records borrowers,
principal, simple monthly interest, payments, collateral, and capital movements. The system is
multi-tenant at the data-model level from its first release.

## Project structure

- `frontend/` — React + Vite mobile-first interface
- `backend/` — FastAPI + SQLAlchemy API
- PostgreSQL is the production database target; SQLite is used for zero-setup local development.

## Core accounting rules currently encoded

- Interest rates are entered manually per loan and are not capped by the software.
- Interest accrues monthly against outstanding principal only.
- Accrued interest does not compound and is never added to the interest basis.
- Suggested payment allocation pays accrued interest first and then principal.
- Users may edit that allocation, but the amount assigned to interest cannot exceed accrued interest.
- Every borrower, loan, payment, accrual, and capital-ledger record belongs to a tenant.
- The first interest cycle is charged when the loan is disbursed; later cycles follow the next-interest date.
- Authenticated users are assigned to one tenant, and the API derives tenant scope from the verified session.
- Every login session must acknowledge the mathematical-tracking disclaimer.
- Sessions expire after five minutes without an authenticated API request and are revoked immediately on logout.
- API responses containing tenant data are marked `no-store` to prevent browser caching.

## Run the API locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed_demo
uvicorn app.main:app --reload
```

API documentation will be available at `http://localhost:8000/docs`. Configure the JWT and bootstrap
administrator values shown in `backend/.env.example` before first login. The pilot database is Tenant 1;
future provisioned databases receive Tenant 2 and higher while retaining UUID boundaries internally.

## Run the interface locally

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Product boundary

TuCap performs mathematical tracking and recordkeeping. It does not determine whether user-entered
loan terms are lawful and its records are not, by themselves, legal proof of a debt. Final disclaimer
language must be reviewed for the intended market before public distribution.

## Render development deployment

The root `render.yaml` Blueprint defines a free FastAPI web service and a free PostgreSQL database.
After deploying the Blueprint, verify:

- `https://YOUR-SERVICE.onrender.com/api/health`
- `https://YOUR-SERVICE.onrender.com/docs`

The pilot tenant and its Tenant 1 identifier are created idempotently at startup. On an existing
Render service, add `JWT_SECRET`, `BOOTSTRAP_ADMIN_EMAIL`, and `BOOTSTRAP_ADMIN_PASSWORD` manually in
the service environment before deploying authentication. `JWT_SECRET` must contain at least 32
characters and the bootstrap password must contain at least 12.
