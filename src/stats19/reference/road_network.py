"""Load OS Open Roads into geo.road_link / geo.road_node (PLAN-008 T2)."""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path

import httpx
import psycopg

from stats19.download import download_file
from stats19.reference import roads
from stats19.reference.derived import rebuild
from stats19.reference.swap import swap_tables

log = logging.getLogger(__name__)

_LINK_DDL = """CREATE TABLE geo.road_link__new (
    id text NOT NULL, road_class text, road_function text, form_of_way text,
    road_number text, name text, structure text, length_m double precision,
    trunk boolean, primary_route boolean, start_node text, end_node text,
    geom_bng geometry(LineString, 27700) NOT NULL)"""

_NODE_DDL = """CREATE TABLE geo.road_node__new (
    id text NOT NULL, form text, geom_bng geometry(Point, 27700) NOT NULL)"""

_MOTORWAY_JUNCTION_DDL = """CREATE TABLE geo.motorway_junction__new (
    id text NOT NULL, junction_number text, geom_bng geometry(Point, 27700) NOT NULL)"""

_SWAP_DDL = {
    "road_link": [
        "ALTER TABLE geo.road_link ADD PRIMARY KEY (id)",
        "CREATE INDEX road_link_geom_idx ON geo.road_link USING gist (geom_bng)",
        "CREATE INDEX road_link_number_idx ON geo.road_link (road_number)",
        "CREATE INDEX road_link_start_idx ON geo.road_link (start_node)",
        "CREATE INDEX road_link_end_idx ON geo.road_link (end_node)",
    ],
    "road_node": [
        "ALTER TABLE geo.road_node ADD PRIMARY KEY (id)",
        "CREATE INDEX road_node_geom_idx ON geo.road_node USING gist (geom_bng)",
    ],
    "motorway_junction": [
        "CREATE INDEX motorway_junction_geom_idx ON geo.motorway_junction USING gist (geom_bng)",
    ],
}


def extract_gpkg(zip_path: Path, dest_dir: Path) -> Path:
    """Unpack the GeoPackage (about 2 GB) next to the download; SQLite needs a real file."""
    with zipfile.ZipFile(zip_path) as z:
        member = next((n for n in z.namelist() if n.endswith(roads.GPKG_MEMBER_SUFFIX)), None)
        if member is None:
            raise ValueError(f"{zip_path.name}: no GeoPackage inside")
        target = dest_dir / Path(member).name
        with z.open(member) as src, target.open("wb") as out:
            shutil.copyfileobj(src, out, length=16 * 1024 * 1024)
    return target


def _copy(conn: psycopg.Connection, table: str, columns: str, rows) -> int:
    n = 0
    with conn.cursor() as cur, cur.copy(f"COPY geo.{table}__new ({columns}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
            n += 1
    return n


def load_road_network(conn: psycopg.Connection, client: httpx.Client, data_dir: Path) -> None:
    archive = download_file(client, roads.SOURCE_URL, data_dir, "os_open_roads.zip")
    load_road_network_zip(conn, archive.path, data_dir)


def load_road_network_zip(conn: psycopg.Connection, zip_path: Path, work_dir: Path) -> None:
    gpkg = extract_gpkg(zip_path, work_dir)
    try:
        with conn.transaction():
            for table, ddl in (
                ("road_link", _LINK_DDL),
                ("road_node", _NODE_DDL),
                ("motorway_junction", _MOTORWAY_JUNCTION_DDL),
            ):
                conn.execute(f"DROP TABLE IF EXISTS geo.{table}__new")
                conn.execute(ddl)
            link_cols = ", ".join(roads.LINK_COLUMNS) + ", geom_bng"
            links = _copy(conn, "road_link", link_cols, roads.parse_links(gpkg))
            nodes = _copy(conn, "road_node", "id, form, geom_bng", roads.parse_nodes(gpkg))
            _copy(
                conn,
                "motorway_junction",
                "id, junction_number, geom_bng",
                roads.parse_motorway_junctions(gpkg),
            )
    finally:
        gpkg.unlink(missing_ok=True)
    log.info("OS Open Roads copied: %s links, %s nodes", f"{links:,}", f"{nodes:,}")
    swap_tables(conn, "road_network", _SWAP_DDL, "OS Open Roads", links, f"{nodes:,} nodes")
    # traffic count points -> the new links, then junctions, collision matches and safety
    rebuild(conn, "traffic_links", "junctions", "collision_links", "context", "safety")
