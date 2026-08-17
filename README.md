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

## Run the API locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m app.seed_demo
uvicorn app.main:app --reload
```

API documentation will be available at `http://localhost:8000/docs`. During the development phase,
tenant-scoped requests use this temporary header:

```text
X-Tenant-ID: 00000000-0000-0000-0000-000000000001
```

Authenticated user sessions will replace this temporary development boundary before third-party use.

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

The development API documentation uses this tenant header:

```text
X-Tenant-ID: 00000000-0000-0000-0000-000000000001
```

The pilot tenant is created idempotently at startup. Authenticated sessions will replace the
temporary header before TuCap is offered to third parties.
