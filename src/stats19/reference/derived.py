"""Tables derived from the reference datasets, rebuilt once per refresh (FU-034 #4).

Loading the road network, traffic or OSM nodes invalidates the traffic links, junctions,
collision matches and safety model. A loader asks for what it invalidates with
``rebuild(...)``. On its own that runs straight away; inside ``deferred(conn)``, as a full
reference refresh does, the requests are collected and each build runs once at the end, in
dependency order. Before this, a full refresh fitted the safety model three times.

Requests are also written to ``etl.derived_pending`` and each is cleared only when its build
commits (FU-051). The datasets that asked for a build are already marked fresh, so without
this a failed build was never retried; now the pipeline's next check runs what's left.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar

import psycopg

log = logging.getLogger(__name__)

# dependency order: links feed junction arms, junctions feed collision matches, and all of
# them feed the safety model; the collision matches give the headings for the sun (PLAN-012);
# the authorities' denominators (V4) need only traffic, population and boundaries
ORDER = (
    "traffic_links",
    "junctions",
    "junction_osm",
    "junction_collisions",
    "collision_links",
    "context",
    "safety",
    "authorities",
)
# a full junction build also applies the OSM nodes and re-matches the collisions
_COVERED_BY = {"junctions": {"junction_osm", "junction_collisions"}}

_pending: ContextVar[set[str] | None] = ContextVar("derived_pending", default=None)


def _builders() -> dict[str, Callable[[psycopg.Connection], None]]:
    # imported here: the build modules import loaders that import this module
    from stats19.reference.authority_build import build_authorities
    from stats19.reference.collision_link_build import match_collision_links
    from stats19.reference.context_build import build_context
    from stats19.reference.junction_build import (
        build_junctions,
        match_junction_collisions,
        update_junction_osm,
    )
    from stats19.reference.safety_build import build_safety
    from stats19.reference.traffic_links import build_traffic_links

    return {
        "traffic_links": build_traffic_links,
        "junctions": build_junctions,
        "junction_osm": update_junction_osm,
        "junction_collisions": match_junction_collisions,
        "collision_links": match_collision_links,
        "context": build_context,
        "safety": build_safety,
        "authorities": build_authorities,
    }


def plan(steps: set[str]) -> list[str]:
    """The steps to run, in order, leaving out any a fuller step already covers."""
    unknown = steps - set(ORDER)
    if unknown:
        raise ValueError(f"unknown derived build(s): {sorted(unknown)}")
    for step, covered in _COVERED_BY.items():
        if step in steps:
            steps = steps - covered
    return [s for s in ORDER if s in steps]


# ------------------------------------------------------------------ the database's record


def load_pending(conn: psycopg.Connection) -> set[str]:
    """Builds asked for but not yet finished, e.g. after a failure (FU-051)."""
    rows = conn.execute("SELECT step FROM etl.derived_pending").fetchall()
    conn.commit()
    return {r[0] if isinstance(r, tuple) else r["step"] for r in rows} & set(ORDER)


def _add_pending(conn: psycopg.Connection, steps: set[str]) -> None:
    conn.execute(
        """INSERT INTO etl.derived_pending (step)
           SELECT unnest(%s::text[]) ON CONFLICT (step) DO NOTHING""",
        (sorted(steps),),
    )
    conn.commit()


def _clear_pending(conn: psycopg.Connection, steps: set[str]) -> None:
    conn.execute("DELETE FROM etl.derived_pending WHERE step = ANY(%s)", (sorted(steps),))


# ------------------------------------------------------------------ running


def run(conn: psycopg.Connection, steps: set[str]) -> list[str]:
    ordered = plan(steps)
    builders = _builders()
    for step in ordered:
        log.info("rebuilding derived table: %s", step)
        builders[step](conn)
        _clear_pending(conn, {step} | _COVERED_BY.get(step, set()))
        conn.commit()
    return ordered


def run_pending(conn: psycopg.Connection) -> list[str]:
    """Run the builds still pending from earlier (a failure, or an interrupted refresh)."""
    steps = load_pending(conn)
    if steps:
        log.info("derived builds pending from earlier: %s", ", ".join(plan(steps)))
    return run(conn, steps) if steps else []


def rebuild(conn: psycopg.Connection, *steps: str) -> None:
    """Rebuild these now, or at the end of the enclosing deferred() block."""
    plan(set(steps))  # fail fast on a typo
    _add_pending(conn, set(steps))
    pending = _pending.get()
    if pending is None:
        run(conn, set(steps))
    else:
        pending.update(steps)


@contextmanager
def deferred(conn: psycopg.Connection) -> Iterator[None]:
    """Collect rebuild requests and run each once when the block ends (if it succeeds),
    together with any builds still pending from earlier."""
    if _pending.get() is not None:  # already deferring: the outer block runs them
        yield
        return
    token = _pending.set(set())
    try:
        yield
        steps = _pending.get() or set()
    finally:
        _pending.reset(token)
    steps = steps | load_pending(conn)
    if steps:
        run(conn, steps)
