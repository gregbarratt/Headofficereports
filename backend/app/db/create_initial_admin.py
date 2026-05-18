from sqlalchemy import select

from app.core.config import settings
from app.db.session import get_session_factory
from app.models.user import User
from app.services.passwords import hash_password


def create_initial_admin() -> None:
    email = settings.initial_super_admin_email.strip().lower()
    password = settings.initial_super_admin_password

    if not email or not password:
        if settings.environment == "production":
            raise RuntimeError(
                "INITIAL_SUPER_ADMIN_EMAIL and INITIAL_SUPER_ADMIN_PASSWORD must be set before deployment."
            )
        print("Initial Super Admin was not created because no email/password was set.")
        return

    with get_session_factory()() as db:
        existing_user = db.scalar(select(User).where(User.email == email))
        if existing_user is not None:
            print(f"Initial Super Admin already exists: {email}")
            return

        admin = User(
            email=email,
            hashed_password=hash_password(password),
            is_active=True,
            is_super_admin=True,
        )
        db.add(admin)
        db.commit()
        print(f"Initial Super Admin created: {email}")


if __name__ == "__main__":
    create_initial_admin()
