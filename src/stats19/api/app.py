"""FastAPI application factory."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from stats19.api import (
    areas,
    client_errors,
    collisions,
    compare,
    corridors,
    data_issues,
    describe,
    export,
    feedback,
    hotspots,
    junctions,
    listing,
    meta,
    rates,
    report_routes,
    safety,
    scheme_evaluation,
    schemes,
    search,
    sites,
    sticks,
    summary,
    tiles,
    traffic,
)
from stats19.api.access import AccessVerifier, install_access_check
from stats19.api.deps import open_pool
from stats19.api.envelope import install_error_handlers
from stats19.api.request_log import install_request_log
from stats19.config import DEFAULT_REPORT_BASE_URL, load_settings
from stats19.version import version


def create_app(
    database_url: str | None = None,
    report_base_url: str | None = None,
    access: AccessVerifier | None = None,
) -> FastAPI:
    if database_url is None:
        settings = load_settings()
        database_url = settings.database_url
        report_base_url = report_base_url or settings.report_base_url
        access = access or AccessVerifier.from_settings(
            settings.access_team_domain, settings.access_aud
        )
    url = database_url
    report_base = report_base_url or DEFAULT_REPORT_BASE_URL

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.pool, app.state.db_slots = open_pool(url)
        try:
            yield
        finally:
            app.state.pool.close()

    app = FastAPI(
        title="STATS19 API",
        version=version()["commit"],
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.report_base_url = report_base
    install_error_handlers(app)
    install_access_check(app, access)  # remote requests need a Cloudflare Access login
    install_request_log(app)  # outermost: every response, 401s included, gets a ref
    for module in (
        meta,
        search,
        areas,
        tiles,
        listing,
        collisions,
        summary,
        describe,
        export,
        sticks,
        hotspots,
        compare,
        report_routes,
        traffic,
        junctions,
        safety,
        corridors,
        sites,
        rates,
        data_issues,
        client_errors,
        schemes,
        scheme_evaluation,
        feedback,
    ):
        app.include_router(module.router, prefix="/api")
    return app
