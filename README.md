# Head Office Reporting & Trust Reconciliation System

This is the new Head Office-only reporting system. It is separate from the existing Travel Agent Onboarding Hub.

## Current Phase

Phase 10 adds Refund tracking and refund liabilities:

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
- SINGs/Singhs Customer Payment import
- Customer payment row list
- Actual fee storage and estimated fee fallback
- Trust Reconciliation engine
- Booking-level trust position
- Required trust balance summary
- Bank / Trust Statement import
- Bank transaction list
- Actual trust balance and variance
- Refund import
- Refund liability tracking
- Overdue refund exceptions
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
- `GET /api/bank-transactions`
- `GET /api/refunds`
- `GET /api/uploads/types`
- `GET /api/uploads`
- `POST /api/uploads`
- `GET /api/bookings`
- `GET /api/customer-payments`
- `GET /api/supplier-payments`
- `GET /api/trust-reconciliation`

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

Phase 7 imports SINGs/Singhs Customer Payment Data rows into the `customer_payments` table.

Phase 8 calculates trust reconciliation from imported source tables. It does not use the Master Booking Report's `Total Received`, `Paid (supp.)`, or `Profit (projected)` values as trusted finance sources.

Phase 9 imports Bank / Trust Statement rows into the `bank_transactions` table and uses the latest trust balance as the actual bank position.

Phase 10 imports Refund rows into the `refunds` table and includes refund liabilities in trust reconciliation.

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

## Customer Payment Import

SINGs/Singhs data is the trusted customer receipt source.

Mapped fields where present:

- transaction_id
- booking_reference or invoice_reference
- customer_name
- payment_date
- settlement_date
- gross_amount
- fee_amount
- net_settled_amount
- payment_method
- card_type
- card_brand
- transaction_status
- refund_indicator
- chargeback_indicator
- merchant_account
- settlement_batch_reference

Important rule:

```text
If SINGs/Singhs supplies the actual fee, the system stores and uses that fee.
If the actual fee is missing, the system estimates the fee only if a matching payment method rule exists.
```

Customer payment matching:

- First by Booking Reference.
- Then by Invoice Reference if it matches a booking reference.
- If neither is available, the system can make a lower-confidence match using customer name and amount.
- Unmatched rows are still imported and clearly marked.

The Customer Payments page shows:

- gross customer payments
- actual and estimated fees
- net settled amount
- booking match confidence
- unmatched payment count

## Trust Reconciliation

Booking-level calculation:

```text
Customer Gross Payments
- Card / payment fees
= Net Trust Receipts

Net Trust Receipts
- Supplier Payments Made
- Refunds Paid
= Current Booking Trust Balance
```

Overall required trust balance:

```text
Positive booking-level trust balances
+ refunds due but unpaid
+ unmatched customer receipts
= Required Trust Balance
```

Trust variance:

```text
Actual Trust Bank Balance - Required Trust Balance = Trust Variance
```

For the MVP, the system does not automatically release margin.

The Trust Reconciliation page marks incomplete data clearly, including:

- Awaiting SINGs/Singhs payment data
- Awaiting supplier payment data
- Awaiting bank statement
- Awaiting commission data

For booking `OTC-01436`, if only the Master Booking Report and Supplier Payment Report have been imported, the supplier side can show complete while the trust status remains incomplete until SINGs/Singhs customer payment data is imported.

## Bank / Trust Statement Import

Mapped fields:

- transaction_date
- description
- money_in
- money_out
- balance
- account_type
- transaction_reference

The system stores every bank statement row.

Duplicate checking uses:

```text
transaction date + description + money in + money out + balance + account type + transaction reference
```

Bank transaction matching:

- The system looks for an existing booking reference inside the bank description or reference.
- If a booking reference is found, the row is marked as matched.
- If no booking reference is found, the row is imported and a review exception is created.
- Duplicate rows are imported, marked as duplicate, and a review exception is created.

Trust variance now uses:

```text
Latest imported Trust Bank Balance - Required Trust Balance = Trust Variance
```

If no bank statement has been imported, the Trust Reconciliation page still shows `Awaiting bank statement`.

## Refund Import

Mapped fields:

- booking_ref
- customer_name
- refund_reason
- refund_amount_due
- refund_amount_paid
- refund_status
- supplier_refund_expected
- supplier_refund_received
- due_date
- paid_date

The system stores each refund row separately.

Refund liability calculation:

```text
Refund Amount Due - Refund Amount Paid = Refund Still Unpaid
```

Supplier refund recovery calculation:

```text
Supplier Refund Expected - Supplier Refund Received = Supplier Refund Outstanding
```

Refunds are included in trust reconciliation:

- refunds paid reduce the current booking trust balance
- refunds due but unpaid increase the required trust balance

If a refund is past its due date and still unpaid, the system creates an overdue refund exception for Head Office review.
