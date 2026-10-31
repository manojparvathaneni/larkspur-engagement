# One image for Larkspur's legacy estate: FREIGHTCORE, Deskline, the batch jobs and the world engine.
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/data:/app/world:/app/legacy/batch
RUN pip install --no-cache-dir fastapi==0.115.* uvicorn==0.32.* "psycopg[binary]==3.2.*" lxml==5.3.* cryptography==43.* httpx==0.27.* tzdata
WORKDIR /app
COPY data /app/data
COPY legacy /app/legacy
COPY world /app/world
RUN useradd -r -u 1001 larkspur && mkdir -p /srv/larkspur && chown larkspur /srv/larkspur
USER larkspur
