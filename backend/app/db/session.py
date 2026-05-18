from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_engine():
    global _engine
    if _engine is None:
        if not settings.sqlalchemy_database_url:
            raise RuntimeError("DATABASE_URL is not configured.")
        _engine = create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _session_factory


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
