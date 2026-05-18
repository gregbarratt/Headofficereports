from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.trust_reconciliation import TrustReconciliationResponse
from app.services.trust_reconciliation import calculate_trust_reconciliation


router = APIRouter(prefix="/api/trust-reconciliation", tags=["Trust Reconciliation"])


@router.get("", response_model=TrustReconciliationResponse)
def get_trust_reconciliation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_super_admin),
) -> TrustReconciliationResponse:
    return calculate_trust_reconciliation(db)
