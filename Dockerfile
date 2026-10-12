FROM node:22-bookworm-slim AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000 \
    SESSION_COOKIE_SECURE=1 \
    MYSQL_SSL_CA=/etc/secrets/ca.pem
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend-build /build/frontend/dist /app/frontend/dist
EXPOSE 10000
# migrate.py only adds missing tables/columns; it never drops data.
CMD ["sh", "-c", "python migrate.py && exec gunicorn --bind \"0.0.0.0:$PORT\" run:app"]