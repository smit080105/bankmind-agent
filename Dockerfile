FROM node:22-alpine AS frontend

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY frontend ./frontend
RUN npm run build:frontend

FROM python:3.12-slim AS dependencies

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 bankmind \
    && useradd --system --uid 10001 --gid bankmind --home-dir /app bankmind

WORKDIR /app
COPY --from=dependencies /install /usr/local
COPY --chown=bankmind:bankmind . .
COPY --from=frontend --chown=bankmind:bankmind /build/frontend/dist /app/frontend/dist
RUN mkdir -p /app/data && chown bankmind:bankmind /app/data

USER bankmind

EXPOSE 8000

CMD ["sh", "-c", "python scripts/init_db.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
