# Head Office Reporting & Trust Reconciliation System

This is the new Head Office-only reporting system. It is separate from the existing Travel Agent Onboarding Hub.

## Current Phase

Phase 1 creates the foundation:

- FastAPI backend
- React frontend
- Environment-based settings
- PostgreSQL connection settings ready for later phases
- Render deployment skeleton
- Health check endpoints

No agent login, registration, or multi-user role system is included.

## Folder Guide

- `backend/` - Python FastAPI application
- `frontend/` - React web interface
- `render.yaml` - Render deployment starter file
- `.env.example` - safe example settings

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

PostgreSQL is not required for the Phase 1 health screen to run. In Phase 2, the database schema and migrations will be added.
