FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Headless Chromium (+ system libraries and fonts) for PDF reports.
RUN /app/.venv/bin/playwright install --with-deps --only-shell chromium \
    && rm -rf /var/lib/apt/lists/*

COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 1000 stats19 && mkdir /data && chown stats19 /data
USER stats19

# Which code this is (FU-050; scripts/update.sh passes them). Last, so a new commit only
# rebuilds this layer.
ARG GIT_COMMIT=unknown
ARG BUILD_DATE=
ENV STATS19_COMMIT=$GIT_COMMIT \
    STATS19_BUILT=$BUILD_DATE

ENTRYPOINT ["/app/.venv/bin/stats19"]
CMD ["status"]
