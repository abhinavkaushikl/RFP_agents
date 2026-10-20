from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()


def _engine_options(url: str) -> dict:
    # Supabase's transaction pooler can't use server-side prepared statements. Vercel's fluid
    # compute reuses an instance across requests, so keep a few warm connections instead of paying
    # the TCP + TLS + auth handshake on every request; pre-ping drops ones that went stale while idle.
    if os.environ.get("VERCEL") or "pooler.supabase.com" in url:
        return {
            "pool_size": 2,
            "max_overflow": 3,
            "pool_pre_ping": True,
            "pool_recycle": 300,
            "connect_args": {"prepare_threshold": None},
        }
    return {}


engine = create_engine(settings.database_url, future=True, **_engine_options(settings.database_url))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
