from __future__ import annotations

try:
    from celery import Celery
except ImportError:  # pragma: no cover
    Celery = None

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery("app", broker=settings.redis_url, backend=settings.redis_url) if Celery else None

__all__ = ["celery_app"]
