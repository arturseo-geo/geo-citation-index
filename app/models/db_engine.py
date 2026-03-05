"""
Database engine and session factory.

SQLite by default — single file, zero administration, adequate for
monthly batch runs. Set DATABASE_URL env var for PostgreSQL if needed.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import DATABASE_URL
from app.models.db import Base


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables if they do not exist."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Session:
    """Context manager for DB sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
