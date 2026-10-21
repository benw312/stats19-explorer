"""Connection pool shared by request handlers.

Handlers are synchronous, so FastAPI runs them, and ``get_conn``, in a small set of worker
threads. A request first waits for a database slot on the event loop (``db_slot``), which
costs no thread, and only then takes a worker thread and a connection. Before (FU-053), a
burst of map tiles filled every thread with requests waiting for a connection; the requests
holding one then had no thread to give it back in, and all waited out the 30 s pool timeout.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Annotated

import psycopg
from fastapi import Depends, Request
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

POOL_SIZE = 10


def open_pool(url: str, size: int = POOL_SIZE) -> tuple[ConnectionPool, asyncio.Semaphore]:
    # JIT compiling costs ~300 ms on queries the planner overestimates, and API queries
    # are short: it's never repaid (FU-052). A parallel hash join's shared table can reach
    # work_mem x 2 x 3 processes in /dev/shm; at the pipeline's 64 MB, ten heavy queries at
    # once overflowed the database's 2 GB. 32 MB is as fast for the API's queries (FU-053).
    options = "-c jit=off -c work_mem=32MB"
    pool = ConnectionPool(url, min_size=1, max_size=size, open=True, kwargs={"options": options})
    return pool, asyncio.Semaphore(size)


async def db_slot(request: Request) -> AsyncIterator[None]:
    """One of the pool's connections, waited for without holding a worker thread."""
    async with request.app.state.db_slots:
        yield


def get_conn(
    request: Request, _slot: Annotated[None, Depends(db_slot)]
) -> Iterator[psycopg.Connection]:
    with request.app.state.pool.connection() as conn:
        conn.row_factory = dict_row
        yield conn
