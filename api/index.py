"""Vercel serverless entry point. Re-exports the FastAPI app."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.bootstrap import create_app  # noqa: E402

app = create_app()
