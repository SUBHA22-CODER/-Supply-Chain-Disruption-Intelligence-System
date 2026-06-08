import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://admin:password@localhost/supplychain"
)

# Detect and fallback to SQLite if postgres connection is refused or defaults to it
IS_SQLITE = False
if DATABASE_URL.startswith("sqlite"):
    IS_SQLITE = True

try:
    if not IS_SQLITE:
        # Test connection briefly
        temp_engine = create_engine(DATABASE_URL, connect_args={'connect_timeout': 2})
        with temp_engine.connect() as conn:
            pass
        engine = create_engine(
            DATABASE_URL,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
    else:
        raise Exception("Forced SQLite")
except Exception:
    print("PostgreSQL database connection failed. Falling back to SQLite local database.")
    DATABASE_URL = "sqlite:///supplychain.db"
    IS_SQLITE = True
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
