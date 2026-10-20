from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()


def _engine_options(url: str) -> dict:
    # Serverless functions (Vercel) and Supabase's transaction pooler must not hold their own
    # connection pool or use server-side prepared statements.
    if os.environ.get("VERCEL") or "pooler.supabase.com" in url:
        return {"poolclass": NullPool, "connect_args": {"prepare_threshold": None}}
    return {}


engine = create_engine(settings.database_url, future=True, **_engine_options(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
