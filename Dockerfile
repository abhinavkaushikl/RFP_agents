# ── Web app (React) ─────────────────────────────────────────────────────
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ── API (serves the built web app at /) ─────────────────────────────────
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/opt/hf

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
# CPU-only torch keeps the image small; sentence-transformers needs it for embeddings.
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install .

# Bake the embedding model into the image so containers start without network access.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

COPY alembic.ini ./
COPY alembic ./alembic
COPY configs ./configs
COPY ui ./ui
COPY scripts ./scripts
COPY --from=web /web/dist ./web/dist

RUN useradd --create-home appuser && chown -R appuser /app /opt/hf
USER appuser

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000 --workers ${API_WORKERS:-2}"]
