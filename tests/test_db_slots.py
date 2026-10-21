"""A burst of requests can't deadlock the API (FU-053).

Requests used to take a database connection in a worker thread and give it back in
another. When a burst (map tiles while clicking through areas) filled every worker thread
with requests waiting for a connection, the requests holding one couldn't get a thread
to give it back, and everything waited for the pool's 30 s timeout.
"""

import asyncio
import os

import anyio.to_thread
import httpx
import pytest

pytestmark = pytest.mark.integration


async def _burst(app, n: int) -> list[int]:
    # far fewer worker threads than requests, as on a busy server
    anyio.to_thread.current_default_thread_limiter().total_tokens = 3
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        responses = await asyncio.wait_for(
            asyncio.gather(*(client.get("/api/health") for _ in range(n))), timeout=15
        )
    return [r.status_code for r in responses]


def test_a_burst_of_requests_doesnt_deadlock_the_pool(db_conn):
    from stats19.api.app import create_app
    from stats19.api.deps import open_pool

    app = create_app(os.environ["STATS19_TEST_DATABASE_URL"])
    # what the lifespan does, with a small pool (httpx's transport doesn't run lifespans)
    app.state.pool, app.state.db_slots = open_pool(os.environ["STATS19_TEST_DATABASE_URL"], size=2)
    try:
        assert asyncio.run(_burst(app, 40)) == [200] * 40
    finally:
        app.state.pool.close()
