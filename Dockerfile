# Backend container for the Cell Digital Twin API (FastAPI + celltwin engine).
# Runs on any container host (Render, Railway, Fly.io, Cloud Run, ...).
FROM python:3.11-slim

WORKDIR /app

# Install the package + its runtime deps. Editable install keeps the on-disk
# layout so the engine can resolve data/ (registry uses a path relative to the
# package). Heavy libs (jax, numpyro, scikit-learn) are imported lazily inside
# the analysis endpoints, so the service boots light.
COPY pyproject.toml README.md ./
COPY backend ./backend
COPY data ./data
RUN pip install --no-cache-dir -e .

ENV PORT=8000 PYTHONUNBUFFERED=1
EXPOSE 8000

# Hosts inject $PORT; bind to it (default 8000 for local `docker run`).
CMD ["sh", "-c", "uvicorn celltwin.api.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
