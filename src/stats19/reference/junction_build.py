"""Build geo.junction from OS Open Roads and match junction collisions to it (PLAN-008 T3).

Steps (rules in ``junctions``):

1. Junction nodes: where three or more public-road links meet, every roundabout ring node,
   and mini-roundabouts (OS 'roundabout' nodes off any ring). Private and car-park access
   links (OS road function 'Restricted Local Access Road' / 'Secondary Access Road') are
   left out, so a car park entrance doesn't make a junction.
2. Cluster nodes into junctions (rings, short links), in Python over just those edges.
3. Per junction, in batches: the links leaving it, grouped into arms, typed and named, each
   arm with the DfT count point of the piece nearest the junction (geo.traffic_link).
4. Geometry for matching (the ring for roundabouts, else the nodes), OSM junction signals
   within ``SIGNAL_RADIUS_M``, and the OS motorway junction number for grade-separated ones.

Junction ids are the smallest OS node id in the junction, so they survive rebuilds as long
as OS keeps its node ids.
"""

from __future__ import annotations

import logging
from collections import Counter
from itertools import groupby

import psycopg

from stats19.reference import junctions as jn
from stats19.reference.swap import swap_tables, tables_exist

log = logging.getLogger(__name__)

SIGNAL_RADIUS_M = 30.0  # junction signals stand at the stop lines, close to the node
MOTORWAY_JUNCTION_RADIUS_M = 750.0  # a numbered junction's roundabouts sit off the motorway
COLLISION_RADIUS_M = 25.0  # STATS19's 20 m, plus location error (DfT feasibility study)
COLLISION_YEARS = 10  # older collisions predate too much of today's network
BEARING_M = 20.0  # an arm's direction: from the junction to this far along the link
N_BATCHES = 16

# Shared-use carriageways (shared space, no kerbs) carry traffic, so they're arms (FU-042).
_PUBLIC = (
    "coalesce(l.road_function, '') NOT IN ('Restricted Local Access Road', "
    "'Secondary Access Road') AND l.form_of_way <> 'Guided Busway'"
)

# STATS19 "at or within 20 m of a junction". The 2024 coding (junction_detail 13-19) has no
# roundabout, mini-roundabout or slip road values; those collisions are 0 there, so
# roundabouts are recognised by road type, and any recorded junction control counts.
JUNCTION_COLLISION = """(
    c.junction_detail_historic BETWEEN 1 AND 9
    OR c.junction_detail BETWEEN 13 AND 19
    OR c.road_type = 1
    OR c.junction_control BETWEEN 1 AND 4
)"""


# ------------------------------------------------------------------ 1-2 nodes and clusters

_NODES = f"""
CREATE TEMP TABLE jnode ON COMMIT DROP AS
SELECT d.node, d.ring, NOT d.ring AND n.form = 'roundabout' AS mini, n.geom_bng
FROM (
    SELECT e.node, bool_or(e.ring) AS ring
    FROM (
        SELECT l.start_node AS node, l.form_of_way = 'Roundabout' AS ring
        FROM geo.road_link l WHERE {_PUBLIC}
        UNION ALL
        SELECT l.end_node, l.form_of_way = 'Roundabout' FROM geo.road_link l WHERE {_PUBLIC}
    ) e
    GROUP BY e.node
    HAVING count(*) >= 3 OR bool_or(e.ring)
) d
JOIN geo.road_node n ON n.id = d.node
"""

_EDGES = f"""
SELECT l.start_node, l.end_node, l.length_m, l.form_of_way = 'Roundabout',
       ST_X(a.geom_bng), ST_Y(a.geom_bng), ST_X(b.geom_bng), ST_Y(b.geom_bng)
FROM geo.road_link l
JOIN jnode a ON a.node = l.start_node
JOIN jnode b ON b.node = l.end_node
WHERE {_PUBLIC} AND (l.form_of_way = 'Roundabout' OR l.length_m <= %(join)s)
"""


def _cluster(conn: psycopg.Connection) -> int:
    conn.execute(_NODES)
    conn.execute("CREATE INDEX ON jnode (node)")
    nodes: dict[str, tuple[float, float]] = {}
    rings, shorts = [], []
    for a, b, length, ring, ax, ay, bx, by in conn.execute(_EDGES, {"join": jn.JOIN_M}):
        nodes[a], nodes[b] = (ax, ay), (bx, by)
        if ring:
            rings.append((a, b))
        elif a != b:
            shorts.append((a, b, length))
    members = jn.cluster_nodes(nodes, rings, shorts)
    conn.execute("CREATE TEMP TABLE jmember (node text, junction_id text) ON COMMIT DROP")
    with conn.cursor() as cur, cur.copy("COPY jmember (node, junction_id) FROM STDIN") as copy:
        for row in members.items():
            copy.write_row(row)
    conn.execute(
        """CREATE TEMP TABLE jcluster ON COMMIT DROP AS
           SELECT n.node, coalesce(m.junction_id, n.node) AS junction_id, n.ring, n.mini,
                  abs(hashtext(coalesce(m.junction_id, n.node))) %% %s AS batch
           FROM jnode n LEFT JOIN jmember m USING (node)""",
        (N_BATCHES,),
    )
    conn.execute("CREATE INDEX ON jcluster (node)")
    conn.execute("CREATE INDEX ON jcluster (batch)")
    return len(members)


# ------------------------------------------------------------------ 3 arms


def _arm_links_sql(with_counts: bool) -> str:
    """Links leaving each junction of a batch, with their direction and nearest count point."""

    def side(node: str, other: str, frac: str, order: str) -> str:
        cp = (
            f"(SELECT t.count_point_id FROM geo.traffic_link t WHERE t.link_id = l.id "
            f"ORDER BY {order} LIMIT 1)"
            if with_counts
            else "NULL::integer"
        )
        start = "ST_StartPoint" if node == "start_node" else "ST_EndPoint"
        return f"""
        SELECT c.junction_id, l.id, l.road_class, l.road_number, l.name, l.form_of_way,
               coalesce(degrees(ST_Azimuth({start}(l.geom_bng),
                   ST_LineInterpolatePoint(l.geom_bng, {frac}))), 0) AS bearing,
               {cp} AS count_point_id
        FROM jcluster c
        JOIN geo.road_link l ON l.{node} = c.node
        LEFT JOIN jcluster o ON o.node = l.{other}
        WHERE c.batch = %(batch)s AND {_PUBLIC}
          AND o.junction_id IS DISTINCT FROM c.junction_id"""

    near = f"least(1.0, {BEARING_M} / greatest(l.length_m, 1.0))"
    far = f"greatest(0.0, 1.0 - {BEARING_M} / greatest(l.length_m, 1.0))"
    return (
        side("start_node", "end_node", near, "t.frac_from")
        + "\nUNION ALL"
        + side("end_node", "start_node", far, "t.frac_to DESC")
        + "\nORDER BY 1, 2"
    )


_FLAGS = """
SELECT junction_id, bool_or(ring), bool_or(mini), count(*)
FROM jcluster WHERE batch = %(batch)s GROUP BY junction_id
"""


def _junction_rows(
    junction_id: str, links: list[jn.ArmLink], ring: bool, mini: bool, n_nodes: int
) -> tuple[tuple, list[tuple]] | None:
    arms = jn.group_arms(links)
    kind = jn.classify(arms, ring=ring, mini=mini)
    if kind is None:
        return None
    top = min(arms, key=lambda a: a.rank)
    junction = (
        junction_id,
        kind,
        len(arms),
        jn.junction_name(arms),
        top.lead.road_class,
        sum(a.is_slip for a in arms),
        n_nodes,
    )
    arm_rows = [
        (
            junction_id,
            i,
            role,
            a.lead.road_class,
            a.lead.road_number,
            a.lead.name,
            a.lead.form_of_way,
            round(a.bearing),
            len(a.links),
            a.count_point_id,
        )
        for i, (a, role) in enumerate(zip(arms, jn.arm_roles(arms), strict=True))
    ]
    return junction, arm_rows


def _build_batch(conn: psycopg.Connection, batch: int, arm_sql: str) -> Counter:
    flags = {r[0]: r[1:] for r in conn.execute(_FLAGS, {"batch": batch})}
    rows = conn.execute(arm_sql, {"batch": batch}).fetchall()
    junctions, arms = [], []
    for junction_id, group in groupby(rows, key=lambda r: r[0]):
        links = [jn.ArmLink(*r[1:7], r[7]) for r in group]
        built = _junction_rows(junction_id, links, *flags[junction_id])
        if built is not None:
            junctions.append(built[0])
            arms += built[1]
    _copy(conn, "jrow", _JUNCTION_COLUMNS, junctions)
    _copy(conn, "geo.junction_arm__new", _ARM_COLUMNS, arms)
    return Counter(j[1] for j in junctions)


_JUNCTION_COLUMNS = "id, kind, arms, name, top_class, slip_arms, nodes"
_ARM_COLUMNS = (
    "junction_id, arm, role, road_class, road_number, name, form_of_way, bearing, links, "
    "count_point_id"
)


def _copy(conn: psycopg.Connection, table: str, columns: str, rows: list[tuple]) -> None:
    with conn.cursor() as cur, cur.copy(f"COPY {table} ({columns}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


# ------------------------------------------------------------------ 4 geometry and flags
# Each junction row is written once, with its geometry and flags: updating a million rows
# afterwards would rewrite the table each time.

_GEOMETRY = """
CREATE TEMP TABLE jgeom ON COMMIT DROP AS
WITH pts AS (
    SELECT c.junction_id, ST_Collect(n.geom_bng) AS g
    FROM jcluster c JOIN jnode n USING (node) JOIN jrow r ON r.id = c.junction_id
    GROUP BY c.junction_id
), ring AS (
    SELECT c.junction_id, ST_Collect(l.geom_bng) AS g
    FROM jcluster c JOIN geo.road_link l ON l.start_node = c.node
    JOIN jrow r ON r.id = c.junction_id
    WHERE l.form_of_way = 'Roundabout' GROUP BY c.junction_id
)
SELECT pts.junction_id AS id, coalesce(ring.g, pts.g) AS match_geom,
       ST_Centroid(coalesce(ring.g, pts.g)) AS centre
FROM pts LEFT JOIN ring USING (junction_id)
"""

_MEMBERS = """
INSERT INTO geo.junction_node__new (node_id, junction_id)
SELECT c.node, c.junction_id FROM jcluster c JOIN jrow r ON r.id = c.junction_id
"""

# Signals near each junction of {source} (columns id, match_geom), whether they control it,
# and whether OSM maps a mini-roundabout on it.
_OSM = """
WITH near AS (
    SELECT j.id, s.osm_id, ST_Distance(s.geom_bng, j.match_geom) AS d,
           coalesce(degrees(ST_Azimuth(ST_Centroid(j.match_geom), s.geom_bng)), 0) AS bearing
    FROM {source} j
    JOIN geo.osm_node s
      ON s.kind = 'signals' AND ST_DWithin(s.geom_bng, j.match_geom, %(radius)s)
), sig AS (
    SELECT a.id, count(DISTINCT a.osm_id) AS n,
           bool_or(a.d <= %(at_node)s)
           OR bool_or(abs(mod((a.bearing - b.bearing + 540)::numeric, 360) - 180) > %(spread)s)
               AS signalised
    FROM near a JOIN near b USING (id)
    GROUP BY a.id
), mini AS (
    SELECT DISTINCT j.id
    FROM {source} j
    JOIN geo.osm_node s
      ON s.kind = 'mini_roundabout' AND ST_DWithin(s.geom_bng, j.match_geom, %(mini_radius)s)
)
SELECT j.id, coalesce(sig.n, 0) AS signals, coalesce(sig.signalised, false) AS signalised,
       mini.id IS NOT NULL AS mini
FROM {source} j LEFT JOIN sig USING (id) LEFT JOIN mini USING (id)
WHERE sig.id IS NOT NULL OR mini.id IS NOT NULL
"""
SIGNAL_AT_NODE_M = 5.0
SIGNAL_SPREAD_DEG = 60.0
MINI_ROUNDABOUT_RADIUS_M = 15.0  # OSM puts the mini-roundabout on the junction node
_OSM_PARAMS = {
    "radius": SIGNAL_RADIUS_M,
    "at_node": SIGNAL_AT_NODE_M,
    "spread": SIGNAL_SPREAD_DEG,
    "mini_radius": MINI_ROUNDABOUT_RADIUS_M,
}
# Junctions typed by their arms that an OSM mini-roundabout turns into one. Roundabouts
# keep their type; OS's own mini-roundabout nodes are already minis.
_BECOMES_MINI = "('t_junction', 'crossroads', 'multi_arm')"
_KIND = (
    f"CASE WHEN {{mini}} AND {{arm_kind}} IN {_BECOMES_MINI} "
    "THEN 'mini_roundabout' ELSE {arm_kind} END"
)

_INSERT = """
INSERT INTO geo.junction__new (id, kind, arm_kind, arms, name, top_class, slip_arms, nodes,
                               signals, signalised, motorway_junction, geom_bng, geom_3857,
                               match_geom)
SELECT r.id, {kind}, r.kind, r.arms, r.name, r.top_class, r.slip_arms, r.nodes, {signals},
       {motorway}, g.centre, ST_Transform(g.centre, 3857), g.match_geom
FROM jrow r
JOIN jgeom g ON g.id = r.id
{osm_join}
"""

# A grade-separated junction (one with a slip road arm) takes the nearest OS motorway number.
_MOTORWAY = """(
    SELECT m.junction_number FROM geo.motorway_junction m
    WHERE r.slip_arms > 0 AND ST_DWithin(m.geom_bng, g.centre, %(mj_radius)s)
    ORDER BY m.geom_bng <-> g.centre LIMIT 1)"""


def _insert_junctions(conn: psycopg.Connection) -> None:
    conn.execute(_GEOMETRY)
    conn.execute("CREATE INDEX ON jgeom (id)")
    conn.execute("CREATE INDEX ON jgeom USING gist (match_geom)")
    with_osm = tables_exist(conn, "geo.osm_node")
    if with_osm:
        conn.execute(
            "CREATE TEMP TABLE josm ON COMMIT DROP AS " + _OSM.format(source="jgeom"),
            _OSM_PARAMS,
        )
        conn.execute("CREATE INDEX ON josm (id)")
    query = _INSERT.format(
        kind=_KIND.format(mini="coalesce(o.mini, false)", arm_kind="r.kind")
        if with_osm
        else "r.kind",
        signals="coalesce(o.signals, 0), coalesce(o.signalised, false)"
        if with_osm
        else "NULL, NULL",
        osm_join="LEFT JOIN josm o ON o.id = r.id" if with_osm else "",
        motorway=_MOTORWAY if tables_exist(conn, "geo.motorway_junction") else "NULL",
    )
    conn.execute(query, {"mj_radius": MOTORWAY_JUNCTION_RADIUS_M})


def update_junction_osm(conn: psycopg.Connection, table: str = "geo.junction") -> None:
    """Re-mark signals and mini-roundabouts after the OSM nodes are reloaded.

    Signals mapped on the junction node itself count straight away. Signals mapped at stop
    lines must sit on at least two different approaches: one or two signals on a single arm
    are more likely a stand-alone pedestrian crossing near a priority junction.
    """
    if not tables_exist(conn, "geo.osm_node"):
        return
    schema, name = table.split(".")
    has_arm_kind = conn.execute(
        """SELECT EXISTS (SELECT 1 FROM information_schema.columns
                          WHERE table_schema = %s AND table_name = %s
                            AND column_name = 'arm_kind')""",
        (schema, name),
    ).fetchone()[0]
    if not has_arm_kind:  # built before mini-roundabouts came from OSM: rebuild instead
        build_junctions(conn)
        return
    kind = _KIND.format(mini="coalesce(o.mini, false)", arm_kind="j.arm_kind")
    conn.execute(
        f"""UPDATE {table} j SET signals = coalesce(o.signals, 0),
                                 signalised = coalesce(o.signalised, false),
                                 kind = {kind}
            FROM {table} j2 LEFT JOIN ({_OSM.format(source=table)}) o ON o.id = j2.id
            WHERE j.id = j2.id""",
        _OSM_PARAMS,
    )


# ------------------------------------------------------------------ build

_DDL = {
    "junction": """CREATE TABLE geo.junction__new (
        id text NOT NULL, kind text NOT NULL, arm_kind text NOT NULL, arms smallint NOT NULL,
        name text,
        top_class text, slip_arms smallint, nodes smallint, signals smallint, signalised boolean,
        motorway_junction text, geom_bng geometry(Point, 27700),
        geom_3857 geometry(Point, 3857), match_geom geometry(Geometry, 27700))""",
    "junction_arm": """CREATE TABLE geo.junction_arm__new (
        junction_id text NOT NULL, arm smallint NOT NULL, role text NOT NULL,
        road_class text, road_number text, name text, form_of_way text, bearing smallint,
        links smallint, count_point_id integer)""",
    "junction_node": """CREATE TABLE geo.junction_node__new (
        node_id text NOT NULL, junction_id text NOT NULL)""",
}

_SWAP_DDL = {
    "junction": [
        "ALTER TABLE geo.junction ADD PRIMARY KEY (id)",
        "CREATE INDEX junction_geom_3857_idx ON geo.junction USING gist (geom_3857)",
        "CREATE INDEX junction_geom_bng_idx ON geo.junction USING gist (geom_bng)",
    ],
    "junction_arm": [
        "ALTER TABLE geo.junction_arm ADD PRIMARY KEY (junction_id, arm)",
        "CREATE INDEX junction_arm_cp_idx ON geo.junction_arm (count_point_id)",
    ],
    "junction_node": [
        "ALTER TABLE geo.junction_node ADD PRIMARY KEY (node_id)",
        "CREATE INDEX junction_node_junction_idx ON geo.junction_node (junction_id)",
    ],
}


def build_junctions(conn: psycopg.Connection) -> None:
    if not tables_exist(conn, "geo.road_link", "geo.road_node"):
        log.info("junctions skipped: needs the road network")
        return
    arm_sql = _arm_links_sql(with_counts=tables_exist(conn, "geo.traffic_link"))
    kinds: Counter = Counter()
    with conn.transaction():
        for table, ddl in _DDL.items():
            conn.execute(f"DROP TABLE IF EXISTS geo.{table}__new")
            conn.execute(ddl)
        conn.execute(
            f"CREATE TEMP TABLE jrow ({_JROW_COLUMNS}) ON COMMIT DROP",
        )
        merged = _cluster(conn)
        log.info("junction nodes clustered (%s in multi-node junctions)", f"{merged:,}")
        for batch in range(N_BATCHES):
            kinds += _build_batch(conn, batch, arm_sql)
        conn.execute("CREATE INDEX ON jrow (id)")
        _insert_junctions(conn)
        conn.execute(_MEMBERS)
        # unnamed: the name of an index on a __new table survives the rename (see swap)
        conn.execute("CREATE INDEX ON geo.junction__new USING gist (match_geom)")
        counted = conn.execute(
            "SELECT kind, count(*) FROM geo.junction__new GROUP BY kind ORDER BY 2 DESC"
        ).fetchall()
    total = sum(kinds.values())
    detail = ", ".join(f"{k} {n:,}" for k, n in counted)
    swap_tables(conn, "junctions", _SWAP_DDL, "OS Open Roads (+ OSM nodes)", total, detail)
    match_junction_collisions(conn)


_JROW_COLUMNS = (
    "id text, kind text, arms smallint, name text, top_class text, slip_arms smallint, "
    "nodes smallint"
)


# ------------------------------------------------------------------ collisions

_MATCH = f"""
INSERT INTO geo.junction_collision__new (collision_index, junction_id, dist_m)
SELECT c.collision_index, m.id, m.d
FROM core.collision c
CROSS JOIN LATERAL (
    SELECT j.id, ST_Distance(j.match_geom, c.geom_bng) AS d
    FROM geo.junction j
    WHERE ST_DWithin(j.match_geom, c.geom_bng, %(radius)s)
    ORDER BY 2, 1
    LIMIT 1
) m
WHERE c.collision_year > (SELECT max(collision_year) FROM core.collision) - %(years)s
  AND c.geom_bng IS NOT NULL
  AND {JUNCTION_COLLISION}
"""


def match_junction_collisions(conn: psycopg.Connection) -> None:
    """Each junction collision of the last COLLISION_YEARS -> the nearest junction within
    COLLISION_RADIUS_M. Rebuilt after junctions or STATS19 change."""
    if not tables_exist(conn, "geo.junction", "core.collision"):
        log.info("junction collisions skipped: needs junctions and STATS19 loaded")
        return
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.junction_collision__new")
        conn.execute(
            """CREATE TABLE geo.junction_collision__new (
                   collision_index text NOT NULL, junction_id text NOT NULL, dist_m real)"""
        )
        conn.execute(_MATCH, {"radius": COLLISION_RADIUS_M, "years": COLLISION_YEARS})
        n = conn.execute("SELECT count(*) FROM geo.junction_collision__new").fetchone()[0]
    swap_tables(
        conn,
        "junction_collisions",
        {
            "junction_collision": [
                "ALTER TABLE geo.junction_collision ADD PRIMARY KEY (collision_index)",
                "CREATE INDEX junction_collision_junction_idx "
                "ON geo.junction_collision (junction_id)",
            ]
        },
        "STATS19 junction collisions within 25 m of a junction",
        n,
        f"last {COLLISION_YEARS} years",
    )
