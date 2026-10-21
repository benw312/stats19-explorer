"""Load OSM junction nodes into geo.osm_node; re-mark signalised junctions and minis."""

from __future__ import annotations

import logging
from pathlib import Path

import httpx
import psycopg

from stats19.download import download_file
from stats19.reference import osm_nodes
from stats19.reference.derived import rebuild
from stats19.reference.swap import swap_tables, tables_exist

log = logging.getLogger(__name__)


def load_osm_nodes(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    extract = download_file(client, osm_nodes.SOURCE_URL, data_dir, "osm_great_britain.osm.pbf")
    try:
        load_osm_nodes_file(conn, extract.path)
    finally:
        extract.path.unlink(missing_ok=True)  # 2 GB, and only these few thousand nodes are kept


def load_osm_nodes_file(conn: psycopg.Connection, path: Path) -> None:
    with conn.transaction():
        conn.execute("DROP TABLE IF EXISTS geo.osm_node__new")
        conn.execute(
            """CREATE TABLE geo.osm_node__new (
                   osm_id bigint NOT NULL, kind text NOT NULL,
                   lon double precision, lat double precision,
                   geom_bng geometry(Point, 27700))"""
        )
        with (
            conn.cursor() as cur,
            cur.copy("COPY geo.osm_node__new (osm_id, kind, lon, lat) FROM STDIN") as copy,
        ):
            for row in osm_nodes.parse_osm_nodes(path):
                copy.write_row(row)
        conn.execute(
            """UPDATE geo.osm_node__new
               SET geom_bng = ST_Transform(ST_SetSRID(ST_MakePoint(lon, lat), 4326), 27700)"""
        )
        counts = dict(
            conn.execute("SELECT kind, count(*) FROM geo.osm_node__new GROUP BY kind").fetchall()
        )
    n = sum(counts.values())
    swap_tables(
        conn,
        "osm_nodes",
        {
            "osm_node": [
                "ALTER TABLE geo.osm_node ADD PRIMARY KEY (osm_id)",
                "CREATE INDEX osm_node_geom_idx ON geo.osm_node USING gist (geom_bng)",
            ]
        },
        osm_nodes.ATTRIBUTION,
        n,
        ", ".join(f"{kind} {counts.get(kind, 0):,}" for kind in sorted(counts)),
    )
    if tables_exist(conn, "geo.junction"):
        # junction types and control feed the safety model's peer groups
        rebuild(conn, "junction_osm", "safety")
