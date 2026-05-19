from __future__ import annotations

from datetime import UTC, datetime

from app.db.session import get_session_factory
from app.models.reporting import ReportRun
from app.services.weekly_email import send_weekly_email


def main() -> None:
    session_factory = get_session_factory()
    with session_factory() as db:
        report_run = ReportRun(
            report_type="weekly_email",
            status="running",
            requested_by_user_id=None,
        )
        db.add(report_run)
        db.flush()

        try:
            result = send_weekly_email(db, report_run)
            report_run.status = "completed"
            report_run.finished_at = datetime.now(UTC)
            db.commit()
            print(
                "Weekly email sent to "
                f"{result.recipient_count} recipient(s) with {result.attachment_count} attachment(s)."
            )
        except Exception as exc:
            report_run.status = "failed"
            report_run.finished_at = datetime.now(UTC)
            report_run.error_summary = str(exc)
            db.commit()
            raise


if __name__ == "__main__":
    main()
