"""Derived reference tables rebuild once per refresh (FU-034 #4)."""

import pytest

from stats19.reference import derived


@pytest.fixture
def pending(monkeypatch):
    """The database's list of builds still to run (etl.derived_pending), kept in memory."""
    store: set[str] = set()
    monkeypatch.setattr(derived, "load_pending", lambda conn: set(store))
    monkeypatch.setattr(derived, "_add_pending", lambda conn, steps: store.update(steps))
    monkeypatch.setattr(
        derived, "_clear_pending", lambda conn, steps: store.difference_update(steps)
    )
    return store


@pytest.fixture
def builders(monkeypatch, pending):
    seen: list[str] = []
    fail: set[str] = set()

    def builder(conn, name):
        if name in fail:
            raise RuntimeError(f"{name} ran out of shared memory")
        seen.append(name)

    table = {name: (lambda conn, name=name: builder(conn, name)) for name in derived.ORDER}
    monkeypatch.setattr(derived, "_builders", lambda: table)
    return seen, fail


@pytest.fixture
def calls(builders):
    return builders[0]


class FakeConn:
    def commit(self) -> None:
        pass


def test_plan_orders_steps_and_lets_a_full_junction_build_cover_osm():
    assert derived.plan({"safety", "traffic_links", "junctions"}) == [
        "traffic_links",
        "junctions",
        "safety",
    ]
    assert derived.plan({"junction_osm", "safety"}) == ["junction_osm", "safety"]
    assert derived.plan({"junctions", "junction_osm", "junction_collisions"}) == ["junctions"]
    assert derived.plan({"junction_collisions", "collision_links"}) == [
        "junction_collisions",
        "collision_links",
    ]
    with pytest.raises(ValueError, match="unknown"):
        derived.plan({"safty"})


def test_rebuild_runs_straight_away_outside_a_refresh(calls):
    derived.rebuild(FakeConn(), "safety", "traffic_links")

    assert calls == ["traffic_links", "safety"]


def test_a_full_refresh_builds_each_table_once(calls):
    conn = FakeConn()
    with derived.deferred(conn):
        # road network, then traffic, then OSM nodes, as refresh_reference runs them
        derived.rebuild(conn, "traffic_links", "junctions", "collision_links", "safety")
        derived.rebuild(conn, "traffic_links", "junctions", "safety")
        derived.rebuild(conn, "junction_osm", "safety")
        assert calls == []

    assert calls == ["traffic_links", "junctions", "collision_links", "safety"]


def test_nested_deferral_runs_once_at_the_outer_end(calls):
    conn = FakeConn()
    with derived.deferred(conn):
        with derived.deferred(conn):
            derived.rebuild(conn, "safety")
        assert calls == []
    assert calls == ["safety"]


def test_a_failed_refresh_rebuilds_nothing(calls):
    conn = FakeConn()
    with pytest.raises(RuntimeError), derived.deferred(conn):
        derived.rebuild(conn, "safety")
        raise RuntimeError("download failed")

    assert calls == []
    # and the next rebuild outside a refresh runs straight away again
    derived.rebuild(conn, "safety")
    assert calls == ["safety"]


# FU-051: a failed build is remembered in the database and retried, not forgotten


def test_a_failed_build_stays_pending_with_everything_after_it(builders, pending):
    calls, fail = builders
    fail.add("traffic_links")
    conn = FakeConn()
    with pytest.raises(RuntimeError), derived.deferred(conn):
        derived.rebuild(conn, "traffic_links", "junctions", "safety")

    assert calls == []
    assert pending == {"traffic_links", "junctions", "safety"}


def test_pending_builds_run_at_the_next_check_and_are_then_cleared(builders, pending):
    calls, fail = builders
    pending.update({"safety", "traffic_links"})

    assert derived.run_pending(FakeConn()) == ["traffic_links", "safety"]
    assert calls == ["traffic_links", "safety"]
    assert pending == set()
    assert derived.run_pending(FakeConn()) == []


def test_each_build_is_cleared_as_it_finishes(builders, pending):
    calls, fail = builders
    pending.update({"traffic_links", "junctions", "safety"})
    fail.add("safety")

    with pytest.raises(RuntimeError):
        derived.run_pending(FakeConn())

    assert calls == ["traffic_links", "junctions"]
    assert pending == {"safety"}


def test_a_full_junction_build_clears_the_lighter_junction_steps(builders, pending):
    pending.update({"junctions", "junction_osm", "junction_collisions"})

    derived.run_pending(FakeConn())

    assert pending == set()


def test_a_refresh_also_runs_builds_left_over_from_before(calls, pending):
    pending.add("authorities")
    conn = FakeConn()
    with derived.deferred(conn):
        derived.rebuild(conn, "safety")

    assert calls == ["safety", "authorities"]
    assert pending == set()


@pytest.mark.integration
def test_pending_builds_survive_in_the_database_until_the_daily_check(db_conn, monkeypatch):
    from stats19 import db
    from stats19.reference import refresh

    db.migrate(db_conn)
    seen: list[str] = []
    table = {name: (lambda conn, name=name: seen.append(name)) for name in derived.ORDER}

    def out_of_memory(conn):
        raise RuntimeError("could not resize shared memory segment")

    table["safety"] = out_of_memory
    monkeypatch.setattr(derived, "_builders", lambda: table)

    with pytest.raises(RuntimeError):
        derived.rebuild(db_conn, "collision_links", "safety")
    db_conn.rollback()
    assert seen == ["collision_links"]
    assert derived.load_pending(db_conn) == {"safety"}

    # every dataset is fresh, as on the BOSGAME after the failure: the check still rebuilds
    db_conn.execute(
        """INSERT INTO geo.reference_refresh (dataset, refreshed_at, source, row_count)
           SELECT unnest(%s::text[]), now(), 'test', 1""",
        (list(refresh.DATASETS),),
    )
    db_conn.commit()
    table["safety"] = lambda conn: seen.append("safety")

    assert refresh.refresh_if_stale(db_conn, None, None) == []
    assert seen == ["collision_links", "safety"]
    assert derived.load_pending(db_conn) == set()
