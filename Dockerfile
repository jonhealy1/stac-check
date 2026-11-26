FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Install build tools and dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    make \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY . .

# Install the package with dev and docs extras using the lockfile
ENV UV_LINK_MODE=copy
RUN uv sync --locked --extra dev --extra docs

ENV PATH="/app/.venv/bin:$PATH"

CMD ["stac-check"]
