from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from loguru import logger

DATABASE_URL = settings.DATABASE_URL
if DATABASE_URL and "pgbouncer=" in DATABASE_URL:
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
    parsed = urlparse(DATABASE_URL)
    query_params = parse_qs(parsed.query)
    query_params.pop("pgbouncer", None)
    new_query = urlencode(query_params, doseq=True)
    DATABASE_URL = urlunparse(parsed._replace(query=new_query))

# Handle fallback for local development before env is fully configured
if not DATABASE_URL:
    logger.warning("DATABASE_URL is not set in environment. Falling back to sqlite:///:memory: for development.")
    DATABASE_URL = "sqlite:///:memory:"

# Configure connection pool dynamically depending on dialect.
# SQLite does not support pool_size or max_overflow keyword arguments.
if DATABASE_URL.startswith("postgresql"):
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=10,
        pool_recycle=3600,
        pool_pre_ping=True,
        echo=False
    )
else:
    # SQLite configuration
    engine = create_engine(
        DATABASE_URL,
        # check_same_thread=False is required for SQLite in multi-threaded environments like FastAPI
        connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
        echo=False
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db() -> Generator:
    """FastAPI Dependency for database session management"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
