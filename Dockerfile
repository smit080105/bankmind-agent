FROM python:3.12-slim

WORKDIR /app

# System deps for scikit-learn's compiled wheels and sqlite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The seeded SQLite DB lives here — mount a volume at /app/data in
# docker-compose.yml so it survives container restarts.
RUN mkdir -p /app/data

EXPOSE 8000

# Seed the database on first run, then start the API + dashboard.
CMD ["sh", "-c", "python scripts/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
