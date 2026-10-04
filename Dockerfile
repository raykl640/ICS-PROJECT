# syntax=docker/dockerfile:1
# Multi-stage build: the React frontend, then the Python API that serves it on one port.
# Models, indexes, statute PDFs and feedback are NOT baked in: data/ is bind-mounted and the Hugging Face cache lives in
# a named volume (see docker-compose.yml and README "Docker").

FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# The UI imports the shared strings and the referral list from outside frontend/.
COPY backend/app/lang/ui_strings.json /src/backend/app/lang/ui_strings.json
COPY config/ /src/config/
RUN npm run build

FROM python:3.11-slim-bookworm AS api
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/models \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HAKI_OLLAMA_URL=http://ollama:11434
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt
COPY backend/__init__.py backend/__init__.py
COPY backend/app backend/app
COPY config config
COPY scripts scripts
COPY --from=frontend /src/frontend/dist frontend/dist
RUN useradd --create-home --uid 1000 haki && mkdir -p /models data && chown haki /models data
USER haki
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
