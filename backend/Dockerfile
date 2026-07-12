FROM python:3.13-alpine AS base

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7.20 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY ./alembic.ini ./pyproject.toml ./uv.lock ./
COPY ./alembic ./alembic
COPY ./app ./app

RUN --mount=type=cache,target=/root/.cache/uv     uv sync --frozen

FROM base
COPY --from=builder /app /app
WORKDIR /app

EXPOSE 8000

# Stamp the build with its git SHA so /health can report the deployed version.
ARG GIT_SHA=unknown
ENV LETTERFEED_GIT_SHA=$GIT_SHA

ENV LETTERFEED_PRODUCTION=true
ENV PATH="/app/.venv/bin:$PATH"
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
