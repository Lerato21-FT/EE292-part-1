FROM ghcr.io/astral-sh/uv:0.9.15-python3.14-bookworm-slim AS python-deps
WORKDIR /work
ENV UV_PROJECT_ENVIRONMENT=/opt/venv
COPY docker/pyproject.toml docker/uv.lock ./
RUN uv sync --frozen --no-install-project

FROM node:24.8.0-alpine3.22 AS frontend-deps
WORKDIR /frontend
COPY docker/package.json docker/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

FROM python:3.14.0-slim-bookworm AS app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/work/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /work
COPY --from=python-deps /opt/venv /opt/venv
COPY --from=frontend-deps /frontend/node_modules/plotly.js-dist-min/plotly.min.js /vendor/plotly.min.js
COPY --chown=0:0 broadband_100/ /data/
RUN chmod -R a=rX /data
COPY src/ /work/src/
COPY tests/ /work/tests/
COPY docker/pyproject.toml /work/docker/pyproject.toml
EXPOSE 8000
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]

FROM python-deps AS browser-deps
RUN uv sync --frozen --no-install-project --group browser

FROM python:3.14.0-slim-bookworm AS browser-runtime
COPY --from=browser-deps /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" PLAYWRIGHT_BROWSERS_PATH=/opt/browsers
RUN playwright install --with-deps chromium && chmod -R a=rX /opt/browsers

FROM browser-runtime AS browser-checks
ENV PYTHONPATH="/work/src" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /work
COPY --from=app /work /work
COPY --from=app /data /data
COPY --from=app /vendor /vendor
CMD ["python", "tests/browser_check.py"]
