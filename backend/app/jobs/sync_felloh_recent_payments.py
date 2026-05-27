from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.session import get_session_factory
from app.models.reporting import UploadBatch
from app.services.sings_service import run_felloh_customer_payment_backfill


LOOKBACK_DAYS = 28
CHUNK_DAYS = 7


def main() -> None:
    end_date = datetime.now(UTC).date()
    start_date = end_date - timedelta(days=LOOKBACK_DAYS - 1)
    session_factory = get_session_factory()

    with session_factory() as db:
        active_batch = db.scalar(
            select(UploadBatch)
            .where(UploadBatch.upload_type == "felloh_customer_payment_backfill")
            .where(UploadBatch.status.in_(["queued", "importing"]))
            .limit(1)
        )
        if active_batch:
            print(f"Felloh nightly sync skipped because batch {active_batch.id} is already {active_batch.status}.")
            return

        batch = UploadBatch(
            upload_type="felloh_customer_payment_backfill",
            original_filename=f"Felloh nightly 4-week sync {start_date.isoformat()} to {end_date.isoformat()}",
            status="queued",
            uploaded_by_user_id=None,
            uploaded_at=datetime.now(UTC),
        )
        db.add(batch)
        db.commit()
        db.refresh(batch)
        batch_id = batch.id

    run_felloh_customer_payment_backfill(
        start_date=start_date,
        end_date=end_date,
        actor_user_id=None,
        parent_batch_id=batch_id,
        chunk_days=CHUNK_DAYS,
    )
    print(f"Felloh nightly 4-week sync completed for {start_date.isoformat()} to {end_date.isoformat()}.")


if __name__ == "__main__":
    main()
