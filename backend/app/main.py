from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.agent_commissions import router as agent_commissions_router
from app.api.auth import router as auth_router
from app.api.bank_transactions import router as bank_transactions_router
from app.api.bookings import router as bookings_router
from app.api.customer_payments import router as customer_payments_router
from app.api.dashboard import router as dashboard_router
from app.api.email import router as email_router
from app.api.exceptions import router as exceptions_router
from app.api.insurance import router as insurance_router
from app.api.health import router as health_router
from app.api.refunds import router as refunds_router
from app.api.reports import router as reports_router
from app.api.settings import router as settings_router
from app.api.supplier_payments import router as supplier_payments_router
from app.api.trust_reconciliation import router as trust_reconciliation_router
from app.api.uploads import router as uploads_router
from app.api.weekly_snapshots import router as weekly_snapshots_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    app.include_router(agent_commissions_router)
    app.include_router(auth_router)
    app.include_router(bank_transactions_router)
    app.include_router(bookings_router)
    app.include_router(customer_payments_router)
    app.include_router(dashboard_router)
    app.include_router(email_router)
    app.include_router(exceptions_router)
    app.include_router(insurance_router)
    app.include_router(refunds_router)
    app.include_router(reports_router)
    app.include_router(settings_router)
    app.include_router(supplier_payments_router)
    app.include_router(trust_reconciliation_router)
    app.include_router(uploads_router)
    app.include_router(weekly_snapshots_router)
    app.include_router(health_router)
    return app


app = create_app()
