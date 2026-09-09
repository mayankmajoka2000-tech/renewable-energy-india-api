# India Renewable Energy & Sustainable Finance API
#
# By default this image runs against the bundled SQLite database (baked into
# the image under /app/data), so `docker run` with zero configuration works
# out of the box. Set DATABASE_URL at runtime to point at Postgres instead —
# see docker-compose.yml for the two-service (app + postgres) setup used in
# production.
FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary needs libpq at runtime; build-essential/libpq-dev only
# needed if you switch to psycopg2 (non-binary). Kept minimal since we pin
# psycopg2-binary in requirements.txt.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY data/ data/

EXPOSE 8420

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8420"]
