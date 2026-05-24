# Head Office Reporting & Trust Reconciliation System

This is the new Head Office-only reporting system. It is separate from the existing Travel Agent Onboarding Hub.

## Current Phase

Phase 17 adds the Felloh / SINGs API customer payment sync:

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
- Separate TT human input and live payment source imports
- Upload batch history
- Master Booking Report import
- Booking list view
- OTC / LeMieux booking company labelling from booking reference
- Supplier Payment Report import
- Supplier Payments TAPs and Supplier Payments TT import sources
- Supplier payment row list
- Booking-level supplier reconciliation
- SINGs/Singhs Customer Payment import
- Customer Payments SINGs and Customer Payments TT import sources
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
- Agent Commission import
- Agent commission liability tracking
- Insurance cost import and booking cost reconciliation
- True booking profitability calculation
- Automated exception scan
- Exceptions page and dashboard summary
- Exception status updates
- Weekly snapshot generation
- Week-on-week movement report
- Excel report exports
- Report run history
- Email recipients
- Manual weekly email send
- Excel report attachments
- Render deployment blueprint
- Render PostgreSQL configuration
- Render Cron Job configuration
- Production checklist
- Felloh / SINGs API customer payment sync
- Manual customer payment sync from the Customer Payments page
- Felloh API settings for Render
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
- `GET /api/agent-commissions`
- `GET /api/bank-transactions`
- `GET /api/refunds`
- `GET /api/uploads/types`
- `GET /api/uploads`
- `POST /api/uploads`
- `GET /api/bookings`
- `GET /api/customer-payments`
- `GET /api/email-recipients`
- `POST /api/email-recipients`
- `PATCH /api/email-recipients/{recipient_id}`
- `GET /api/exceptions`
- `POST /api/exceptions/generate`
- `PATCH /api/exceptions/{exception_id}`
- `GET /api/insurance-costs`
- `GET /api/reports/types`
- `GET /api/reports/runs`
- `POST /api/reports/{report_type}/excel`
- `GET /api/settings/status`
- `GET /api/supplier-payments`
- `GET /api/trust-reconciliation`
- `GET /api/weekly-snapshots`
- `POST /api/weekly-snapshots/generate`
- `POST /api/weekly-email/send`

Public health checks remain available:

- `GET /health`
- `GET /api/health`

Before logging in locally, set:

- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `INITIAL_SUPER_ADMIN_EMAIL`
- `INITIAL_SUPER_ADMIN_PASSWORD`

Before sending weekly emails, set:

- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USERNAME`, if your mail provider requires it
- `SMTP_PASSWORD`, if your mail provider requires it
- `SMTP_FROM_EMAIL`
- `SMTP_USE_TLS`

Future SINGs/Singhs API settings:

- `FELLOH_API_BASE_URL`
- `FELLOH_PUBLIC_KEY`
- `FELLOH_PRIVATE_KEY`
- `FELLOH_ORGANISATION_ID`

For production, the Felloh API base URL is:

```text
https://api.felloh.com
```

For sandbox testing, Felloh documents:

```text
https://sandbox.felloh.com
```

## Upload Centre

Phase 4 validates and tracks upload batches.

Phase 5 imports Master Booking Report rows into the `bookings` table.

Phase 6 imports Supplier Payment Report rows into the `supplier_payments` table and reconciles them against each booking's expected supplier nett value.

Phase 7 imports SINGs/Singhs Customer Payment Data rows into the `customer_payments` table.

Phase 8 calculates trust reconciliation from imported source tables. It does not use the Master Booking Report's `Total Received`, `Paid (supp.)`, or `Profit (projected)` values as trusted finance sources.

Phase 9 imports Bank / Trust Statement rows into the `bank_transactions` table and uses the latest trust balance as the actual bank position.

Phase 10 imports Refund rows into the `refunds` table and includes refund liabilities in trust reconciliation.

Phase 11 imports Agent Commission rows into the `agent_commissions` table and calculates true booking profit.

Phase 12 scans the database for finance, trust and compliance exceptions and stores them in the `exceptions` table.

Phase 13 creates weekly snapshots and compares the current week with the previous snapshot.

Phase 14 creates Excel reports and stores report run history.

Phase 15 sends weekly Head Office report emails with Excel attachments.

Phase 16 prepares the app for Render deployment with backend, frontend, PostgreSQL and weekly email cron configuration.

Phase 17 connects to the Felloh / SINGs API for customer payment sync. CSV/XLSX upload remains available as a fallback import method.

Available upload types:

- Master Booking Report
- Supplier Payments TAPs
- Supplier Payments TT (Human Input)
- Customer Payments SINGs
- Customer Payments TT (Human Input)
- Bank / Trust Statement
- Insurance Costs
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
- Pax / Passengers, stored as passenger count when supplied
- Outstanding, comparison only
- Outstanding (Supplier), comparison only
- Total Cost, stored as gross booking value
- Nett, stored as expected supplier nett

The shorter Head Office master export is also supported. It maps:

- `Ref.` to booking reference
- `Status` to booking status
- `Elements` to product flags and ATOL review
- `Destination` to destination
- `Customer` to customer surname
- `Booked` to booking date
- `Depart` to departure date
- `Pax` to passenger count
- `Gross` to gross booking value
- `Nett` to expected supplier nett
- `Paid` to non-trusted customer paid comparison only
- `Balance` to imported customer outstanding comparison only

Plain numeric `Ref.` values are converted to OTC references, for example `1353` becomes `OTC-01353`.
The importer skips guidance rows such as `KEEP`, notes rows and summary total rows.

Excluded master report values are stored only as non-trusted audit fields:

- Total Received
- Paid (supp.)
- Profit (projected)

Bookings are labelled from the booking reference:

- `OTC...` = OTC
- `LEM...`, `LMX...`, `LM-...`, `LM_...`, or references containing `LEMIEUX` = LeMieux
- anything else = review

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

The TAPs export format is also supported directly. For TAPs files, the importer maps:

- `Bkg Reference` as the booking reference
- the first `Collection` column as the supplier payment date
- `Supplier Name` as the supplier
- `Collected` as the actual amount paid

Important: TAPs `Value` is treated as an attempted/requested value only. The system uses `Collected` for actual supplier paid totals, so `NotPaid` rows with `Collected` as `0.00` do not inflate supplier reconciliation.

Every supplier payment row is stored separately. Multiple payment lines for the same booking are not merged.

The system matches supplier payments to bookings by `Booking Reference`.

Supplier payment sources:

- TAPs = actual supplier payment source
- TT = human-entered Traveltek value for cross-checking

Supplier reconciliation uses TAPs as the actual paid source. TT rows are stored separately and shown beside TAPs so Head Office can spot differences between human input and actual payment data.

Supplier reconciliation formula:

```text
Expected Supplier Nett - separately imported Supplier Payments = Calculated Supplier Balance Due
```

Duplicate checking uses:

```text
booking reference + supplier + payment supplier + transaction date + payment method + payment value + associated VAT
```

The source is also included in duplicate checking, so a TT row and a TAPs row for the same booking are not treated as the same record.

For booking `OTC-01436`, the supplier side should reconcile when the imported supplier payment rows are `300.00` and `3394.16` against expected supplier nett `3694.16`.

## Insurance Cost Import

Insurance reports are imported separately from supplier payments and customer receipts.

Mapped fields:

- Booking Reference
- External Reference
- Trade Code
- Trading Name
- Lead Name
- Departure Date
- Supplement Type
- Gross
- Discount
- Net
- Status
- Created At
- Last Update

The importer skips the final total/formula line in the exported report.

For active insurance rows with status `booking`, the system calculates:

```text
Insurance Cost = Gross - Discount
```

Insurance costs are then included in booking cost reconciliation:

```text
Expected Supplier Nett + Insurance Costs = Total Expected Booking Cost
```

The original insurance rows remain visible on the Insurance Costs page for audit and matching review.

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
- SINGs actual gross total
- TT human-input gross total
- SINGs vs TT variance
- actual and estimated fees
- net settled amount
- booking match confidence
- unmatched payment count

## Felloh / SINGs API Integration

Phase 17 adds a manual Felloh / SINGs customer payment sync.

The API service is:

```text
backend/app/services/sings_service.py
```

It uses the official Felloh flow:

- `POST /token` to create a bearer token from the public/private keys
- `POST /agent/transactions` to fetch completed customer payment transactions
- `POST /agent/charges` to fetch actual processing charges where available

The Customer Payments page has a manual **Sync Felloh** button with a date range.

The sync:

- creates new customer payment rows for new Felloh transaction IDs
- cross-checks existing rows when the same Felloh transaction ID is synced again
- updates existing rows only when Felloh has changed the transaction data
- records every Felloh sync in upload batch history
- matches payments to bookings by booking reference where possible
- uses Felloh charges as actual fees where available
- falls back to payment method fee rules where Felloh charges are unavailable

The Customer Payments page also has a **Start 2023 Catch-up** button. It starts a background Felloh sync from `2023-01-01` to the selected end date in 14-day blocks, then records the overall catch-up and each block in upload batch history.

The required private Render environment variables are:

- `FELLOH_PUBLIC_KEY`
- `FELLOH_PRIVATE_KEY`
- `FELLOH_ORGANISATION_ID`

Do not commit API keys to GitHub.

## Traveltek Booking Data Import and Update Review

Traveltek can now replace the manual master booking CSV for booking data.

The Traveltek Updates page has two actions:

- Run a full controlled catch-up, one booking-date batch at a time
- Run an ongoing active update for recent new bookings and active/recent departures
- Import bookings from Traveltek for a selected booking-date range
- Check existing active bookings by booking reference and create review suggestions

The Traveltek `getbookings` document says the import date range is a booking date range. The Traveltek Updates page therefore searches by booking date only. The system stores Traveltek departure and return dates on the booking record, then Head Office can review by travel date inside Booking Checks.

For a historic catch-up, use **Update Everything From Traveltek**. This starts with today, works backwards to `2023-01-30`, and uses safe one-day booking-date batches so recent bookings appear first. The browser page must stay open while it works. The advanced catch-up controls remain available if Head Office needs to change dates, batch size, or restart the saved catch-up position.

For regular use after the catch-up, use **Ongoing active update**. It first imports recent new bookings by booking date, then refreshes only bookings whose departure date is within the active window. The default active window is 60 days after departure, so old departed bookings are not repeatedly checked.

The booking import stores Traveltek booking framework fields including Traveltek booking ID, status, customer name, destination, elements, supplier references, departure date, return date, booking date, due date, total cost, total amount paid, outstanding, total due, due to suppliers, paid to supplier, expected supplier nett and profit.

Traveltek total amount paid, outstanding, total due, due to suppliers, paid to supplier and profit are stored as cross-check figures. SINGs customer receipts are compared only with Traveltek total amount paid because SINGs does not hold the full amount due. TAPs supplier payments and calculated true profit are checked separately, and Traveltek values do not silently replace those actual sources.

Traveltek Total Due, Return Date and Passenger Count are automatically refreshed on the booking record when Traveltek is checked. They appear in Booking Checks, but they do not create separate review suggestions. Traveltek projected profit is kept for reporting/cross-checking, but it no longer creates a Traveltek Updates review item.

Booking Checks now labels PAX as Passenger Count so it matches Traveltek wording. The Traveltek importer also counts passenger rows from the detailed portfolio if Traveltek does not send one simple PAX total. Each row also shows the last booking update date and time, so Head Office can see when a booking was last changed by an import, Traveltek refresh, or manual booking check amendment.

On Booking Checks, the main supplier payment match is TAPs Paid compared with Traveltek Paid To Supplier. Expected Supplier Cost remains visible as a balance guide, but it does not create the red supplier payment mismatch badge on Booking Checks.

Booking Checks loads up to 10,000 booking rows. This prevents the old 5,000-row cap hiding bookings once the system has more than 5,000 records.

The Bookings page loads up to 10,000 booking rows, can sort by booking reference from lowest to highest or highest to lowest, and can export the visible booking list to CSV.

Traveltek is the main source for these booking framework fields:

- booking reference
- Traveltek booking ID
- customer / lead name
- booking status
- destination
- departure date
- return date
- passenger count
- booking elements
- supplier references
- gross booking value
- expected supplier cost, cross-checked with supplier reports

The required private Render environment variables are:

- `TRAVELTEK_API_BASE_URL`
- `TRAVELTEK_SECURE_API_BASE_URL`
- `TRAVELTEK_USERNAME`
- `TRAVELTEK_PASSWORD`
- `TRAVELTEK_SITENAME`, which appears to be the Traveltek sitename / SID
- `TRAVELTEK_MAX_CALLS_PER_RUN`

Keep `TRAVELTEK_MAX_CALLS_PER_RUN` low at first because the Traveltek allowance is limited.

For retrieving the booking list, the API base URL should be:

```text
https://fusionapi.traveltek.net/0.9/interface.pl
```

For retrieving full booking details with `getportfolio`, the secure API base URL should be:

```text
https://secure.traveltek.net/fusionapi/0.9/interface.pl
```

The full `getportfolio` detail call is sent as form-data with one `xml` field, matching the working Postman/Salesforce setup. Where a Traveltek booking ID is available, the detail call uses `bookingid` because that is the most reliable way to retrieve the complete portfolio details.

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

## Agent Commission Import

Mapped fields:

- booking_ref
- agent_name
- commission_basis
- gross_commission
- deductions
- net_commission_due
- commission_status
- due_date
- paid_date

Commission statuses:

- accrued
- due
- paid
- withheld
- clawed_back
- cancelled

The system stores each commission row separately.

True booking profit is calculated by the system:

```text
Gross Booking Value
- Expected Supplier Nett
- Insurance costs
- Actual card / payment fees
- Agent commission
- Refunds / adjustments
= True Booking Profit
```

True margin percentage:

```text
True Booking Profit / Gross Booking Value x 100
```

Important rule:

The Master Booking Report `Profit (projected)` value is not used for true profit.

The Agent Commissions page shows imported commission rows and a booking-level true profitability table. If SINGs/Singhs fees or commission rows are missing, the true profit status is marked incomplete.

## Exceptions

Phase 12 adds an automated exception scan.

It checks for:

- trust shortfall
- unmatched customer payments
- lower-confidence customer payment matches
- unmatched supplier payments
- duplicate supplier payments
- missing supplier references
- supplier overpayments
- supplier balances still due after departure
- cancelled bookings with supplier balances due
- cancelled bookings with commission still due
- unmatched bank transactions
- duplicate bank transactions
- overdue refunds
- unmatched refunds
- missing ATOL certificate review items
- estimated card fees

Severity levels:

- critical
- high
- medium
- low

Status values:

- open
- reviewing
- resolved
- ignored

The Exceptions page lets the Super Admin filter the list, run the scan manually, and mark exceptions as reviewing, resolved, or ignored.

## Weekly Snapshots

Phase 13 adds weekly snapshots.

Each snapshot stores booking-level values for:

- booking status
- gross booking value
- expected supplier nett
- customer payments total
- card fees total
- supplier payments total
- refunds due total
- refunds paid total
- commission due total
- calculated trust balance
- ATOL required
- ATOL certificate issued

The Weekly Reports page can generate the current week's snapshot and compare it with the previous snapshot.

The movement report detects:

- new bookings
- cancelled bookings
- completed bookings
- changed booking value
- changed supplier cost
- changed customer payment position
- changed supplier payment position
- changed refund position
- changed commission position
- changed ATOL status

## Reports and Excel Exports

Phase 14 adds Excel exports from the Weekly Reports page.

Available reports:

- Executive Weekly Overview
- Trust Reconciliation Report
- Customer Payments Report
- Supplier Payments Report
- Supplier Liability Report
- Insurance Costs Report
- Refund Liability Report
- Agent Commission Report
- True Booking Profitability Report
- ATOL Compliance Report
- Week-on-Week Movement Report
- Exception Report

Every report export creates a `report_runs` history record with:

- report type
- status
- start time
- finish time
- output file name
- error summary, where needed

The first version uses Excel files only. PDF executive summary export can be added later if needed.

## Weekly Email Reporting

Phase 15 adds manual weekly email sending from the Weekly Reports page.

The page now lets the Super Admin:

- add Head Office email recipients
- activate or deactivate recipients
- send the weekly email manually
- see email send history in report runs

The weekly email summary includes:

- Actual Trust Balance
- Required Trust Balance
- Trust Variance
- Live Bookings
- New Bookings
- Cancelled Bookings
- Refunds Due
- Supplier Payments Due
- Agent Commission Due
- ATOL Exceptions
- Unmatched Transactions
- Critical Exceptions

The email attaches the Excel reports generated by the reporting engine.

Email credentials are read from environment variables only. Do not add SMTP passwords to code or commit them to GitHub.

## Render Deployment

Phase 16 prepares `render.yaml` for Render Blueprint deployment.

The Blueprint defines:

- FastAPI backend web service
- React static frontend
- Render PostgreSQL database
- weekly email cron job

Render will run database migrations before the backend starts.

The weekly email cron job is scheduled for:

```text
08:00 every Monday, Render cron time
```

Important Render settings to add privately:

- `INITIAL_SUPER_ADMIN_EMAIL`
- `INITIAL_SUPER_ADMIN_PASSWORD`
- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

Do not commit real passwords or email credentials to GitHub.

For a step-by-step production checklist, see:

```text
docs/render-deployment.md
```
