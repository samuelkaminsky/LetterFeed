FROM python:3.13-alpine AS base

FROM base AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY ./pyproject.toml ./uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY ./alembic.ini ./
COPY ./alembic ./alembic
COPY ./app ./app

FROM base

RUN apk add --no-cache su-exec \
    && addgroup -S letterfeed && adduser -S -G letterfeed letterfeed \
    && mkdir -p /data && chown letterfeed:letterfeed /data

WORKDIR /app
COPY --from=builder --chown=letterfeed:letterfeed /app /app

EXPOSE 8000

# Stamp the build with its git SHA so /health can report the deployed version.
ARG GIT_SHA=unknown
ENV LETTERFEED_GIT_SHA=$GIT_SHA

ENV LETTERFEED_PRODUCTION=true
ENV PATH="/app/.venv/bin:$PATH"

CMD ["sh", "-c", "chown -R letterfeed:letterfeed /data && exec su-exec letterfeed sh -c 'alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000'"]
