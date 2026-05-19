# Render Deployment Checklist

This checklist is for deploying the Head Office Reporting System to Render.

## What Render Will Create

The `render.yaml` Blueprint creates:

- a FastAPI backend web service
- a React static frontend
- a Render PostgreSQL database
- a weekly email cron job

## Before Deployment

Make sure the latest code has been pushed to GitHub.

The repository root must contain:

- `render.yaml`
- `backend/`
- `frontend/`

## Private Environment Values

Add these in Render. Do not put real values into GitHub.

Backend service:

- `INITIAL_SUPER_ADMIN_EMAIL`
- `INITIAL_SUPER_ADMIN_PASSWORD`
- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

Cron service:

- `SMTP_HOST`
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`

Values that Render can create or link automatically:

- `DATABASE_URL`
- `JWT_SECRET_KEY`

## Outlook / Microsoft 365 Email

If Head Office wants to send from Outlook / Microsoft 365, use the SMTP settings supplied by the Microsoft account or tenant administrator.

Typical fields are:

- SMTP host
- SMTP port
- SMTP username
- SMTP password or app password
- from email address
- TLS enabled

Do not hardcode these values in the app.

## Deployment Steps

1. Open Render.
2. Choose Blueprint deployment.
3. Connect the GitHub repository.
4. Confirm Render detects `render.yaml`.
5. Add the private environment values.
6. Deploy the Blueprint.
7. Wait for the database, backend, frontend and cron job to finish creating.

## First Login

Render runs:

```text
alembic upgrade head
python -m app.db.create_initial_admin
```

This creates the database tables and first Super Admin from the private Render environment values.

## Checks After Deployment

Check the backend:

```text
https://head-office-reporting-api.onrender.com/health
https://head-office-reporting-api.onrender.com/api/health
```

Check the frontend:

```text
https://head-office-reporting.onrender.com
```

Then log in using the Super Admin email and password set in Render.

## Cron Job

The Render cron job runs:

```text
cd backend && python -m app.jobs.send_weekly_email
```

It sends the weekly report email to active recipients in the database.

Before turning the cron job on for real, make sure:

- email recipients have been added in the app
- SMTP values are correct
- a manual weekly email send works

## Production Checklist

- Super Admin login works.
- Upload Centre opens.
- Master Booking import works.
- Supplier Payment import works.
- Customer Payment import works.
- Trust Reconciliation page loads.
- Reports export to Excel.
- Weekly email manual send works.
- Cron job is active only after email settings are confirmed.
- No real passwords or API keys are committed to GitHub.
