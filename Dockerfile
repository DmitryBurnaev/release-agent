# copy source code
FROM alpine:3.22 AS code-layer
WORKDIR /usr/src

COPY src ./src
COPY alembic.ini .
COPY etc/docker-entrypoint .

# copy source code
FROM python:3.13-alpine AS requirements-layer
WORKDIR /usr/src
ARG DEV_DEPS="false"
ARG UV_VERSION=0.9.9

COPY pyproject.toml .
COPY uv.lock .

RUN pip install uv==${UV_VERSION} && \
	  if [ "${DEV_DEPS}" = "true" ]; then \
      uv export --format requirements-txt --frozen --output-file requirements.txt; \
    else \
      uv export --format requirements-txt --frozen --no-dev --output-file requirements.txt; \
    fi


FROM python:3.13-alpine AS base
ARG PIP_DEFAULT_TIMEOUT=300
WORKDIR /app

COPY --from=requirements-layer /usr/src/requirements.txt .

RUN pip install --timeout "${PIP_DEFAULT_TIMEOUT}" \
      --no-cache-dir --require-hashes \
      -r requirements.txt

RUN addgroup -S release-agent -g 1007 && \
    adduser -S -G release-agent -u 1007 -H release-agent

USER release-agent

COPY --from=code-layer --chown=release-agent:release-agent /usr/src .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_PORT=8000

FROM base AS service

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint"]

FROM base AS tests

COPY pyproject.toml .

ENTRYPOINT ["/bin/sh", "/app/docker-entrypoint"]
