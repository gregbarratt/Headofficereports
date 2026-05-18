# Head Office Reporting & Trust Reconciliation System

This is the new Head Office-only reporting system. It is separate from the existing Travel Agent Onboarding Hub.

## Current Phase

Phase 6 adds the Supplier Payment import and supplier reconciliation:

- FastAPI backend
- React frontend
- Environment-based settings
- PostgreSQL connection settings
- Alembic database migrations
- Core reporting and reconciliation tables
- First Super Admin creation command
- Super Admin-only login
- Protected dashboard access
- Controlled CSV/XLSX uploads
- Upload batch history
- Master Booking Report import
- Booking list view
- Supplier Payment Report import
- Supplier payment row list
- Booking-level supplier reconciliation
- Render deployment skeleton
- Health check endpoints

No agent login, registration, or multi-user role system is included.

## Folder Guide

- `backend/` - Python FastAPI application
- `frontend/` - React web interface
- `render.yaml` - Render deployment starter file
- `.env.example` - safe example settings
- `backend/alembic/` - database migration files

## Backend Setup

From the project folder:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check:

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/api/health`

## Frontend Setup

From the project folder:

```powershell
cd frontend
npm install
npm run dev
```

Then open:

- `http://127.0.0.1:5173`

## Environment Variables

Copy `.env.example` to `.env` when you are ready to add local private settings.

Do not commit `.env` to GitHub.

## Database

PostgreSQL is now configured through `DATABASE_URL`.

To create or update the database tables after setting `DATABASE_URL`:

```powershell
cd backend
alembic upgrade head
```

To create the first Super Admin after setting `INITIAL_SUPER_ADMIN_EMAIL` and `INITIAL_SUPER_ADMIN_PASSWORD`:

```powershell
cd backend
python -m app.db.create_initial_admin
```

The password is stored as a secure hash. The plain password is never stored in the database.

## Authentication

The system has Super Admin login only.

Backend endpoints:

- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`
- `GET /api/uploads/types`
- `GET /api/uploads`
- `POST /api/uploads`
- `GET /api/bookings`
- `GET /api/supplier-payments`

Public health checks remain available:

- `GET /health`
- `GET /api/health`

Before logging in locally, set:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `INITIAL_SUPER_ADMIN_EMAIL`
- `INITIAL_SUPER_ADMIN_PASSWORD`

## Upload Centre

Phase 4 validates and tracks upload batches.

Phase 5 imports Master Booking Report rows into the `bookings` table.

Phase 6 imports Supplier Payment Report rows into the `supplier_payments` table and reconciles them against each booking's expected supplier nett value.

Available upload types:

- Master Booking Report
- Supplier Payment Report
- SINGs/Singhs Customer Payment Data
- Bank / Trust Statement
- Agent Commission Import
- Refund Import

Accepted file types:

- `.csv`
- `.xlsx`

Every upload creates an `upload_batches` record with:

- upload type
- original file name
- uploaded time
- row count
- accepted rows
- rejected rows
- status
- error summary, where needed

## Master Booking Import

Mapped trusted framework fields:

- Status
- Last Name
- Destination
- Elements
- Booking Reference
- Departure Date
- Returned Date
- Date Booked
- Due Date
- Outstanding, comparison only
- Outstanding (Supplier), comparison only
- Total Cost, stored as gross booking value
- Nett, stored as expected supplier nett

Excluded master report values are stored only as non-trusted audit fields:

- Total Received
- Paid (supp.)
- Profit (projected)

## Supplier Payment Import

Mapped fields:

- Transaction Date
- Booking Reference
- Product
- Supplier
- Payment Supplier
- Booking Date
- Departure Date
- Payment Method
- Payment Value
- Associated VAT

Every supplier payment row is stored separately. Multiple payment lines for the same booking are not merged.

The system matches supplier payments to bookings by `Booking Reference`.

Supplier reconciliation formula:

```text
Expected Supplier Nett - separately imported Supplier Payments = Calculated Supplier Balance Due
```

Duplicate checking uses:

```text
booking reference + supplier + payment supplier + transaction date + payment method + payment value + associated VAT
```

For booking `OTC-01436`, the supplier side should reconcile when the imported supplier payment rows are `300.00` and `3394.16` against expected supplier nett `3694.16`.
