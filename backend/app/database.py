from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import settings


def _normalize_database_url(url: str) -> str:
    """
    Neon/Supabase/most providers hand you a plain "postgresql://" URL.
    We install psycopg (v3), not the older psycopg2, so make sure
    SQLAlchemy actually picks that driver instead of leaving it to
    guess - avoids "ModuleNotFoundError: No module named 'psycopg2'"
    or 'psycopg' depending on what happens to be installed/available
    on whatever Python version the host is running.
    """

    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)

    return url


connect_args = (
    {"check_same_thread": False}
    if settings.DATABASE_URL.startswith("sqlite")
    else {}
)

engine = create_engine(
    _normalize_database_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()