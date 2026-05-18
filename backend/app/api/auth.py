from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_super_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, MessageResponse, TokenResponse, UserRead
from app.services.passwords import verify_password
from app.services.tokens import TokenError, create_access_token


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = request.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    if user is None or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )

    if not user.is_active or not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access is required.",
        )

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)

    try:
        access_token = create_access_token(
            subject=str(user.id),
            email=user.email,
            is_super_admin=user.is_super_admin,
        )
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login security is not configured.",
        ) from exc

    return TokenResponse(access_token=access_token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_super_admin)) -> User:
    return current_user


@router.post("/logout", response_model=MessageResponse)
def logout() -> MessageResponse:
    return MessageResponse(message="Logged out.")
