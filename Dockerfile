FROM node:22-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS backend-runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r -g 1000 appuser && useradd -r -u 1000 -g appuser appuser

WORKDIR /app

COPY backend/ /app/backend
COPY --from=frontend-builder /build/dist /app/frontend/dist

WORKDIR /app/backend
RUN pip install --no-cache-dir -e .

RUN mkdir -p /config /logs /staging /media /downloads \
    && chown -R appuser:appuser /app /config /logs /staging /media /downloads

EXPOSE 8899

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD curl -f http://localhost:8899/health || exit 1

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8899"]
