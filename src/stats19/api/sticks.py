"""/api/sticks: per-collision data for stick diagrams (KeyACCIDENT-style).

A stick diagram is a table with one column ("stick") per collision; rows are
collision, vehicle and casualty attributes, drawn as pictograms and re-sortable to
expose patterns. This returns the recorded values (codes for pictograms, labels for
keys and tooltips); layout and sorting happen in the client.
"""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends

from stats19.api.deps import get_conn
from stats19.api.envelope import ApiError, ok
from stats19.api.filters import Filter, count_capped, filter_param, selected_ids

router = APIRouter()
Conn = Annotated[psycopg.Connection, Depends(get_conn)]
Flt = Annotated[Filter, Depends(filter_param)]

# Enough for a long site list in a report; the UI recommends <= 300 for reading.
MAX_STICKS = 1000

_COLLISION = """
SELECT d.collision_index, d.collision_date, to_char(d.collision_time, 'HH24:MI') AS collision_time,
       d.day_of_week, d.day_of_week_label,
       d.collision_severity AS severity,
       d.light_conditions, d.light_conditions_label,
       d.weather_conditions, d.weather_conditions_label,
       d.road_surface_conditions, d.road_surface_conditions_label,
       d.junction_detail, d.junction_detail_label, d.junction_control_label,
       d.road_type, d.road_type_label,
       d.carriageway_hazards, d.carriageway_hazards_label,
       d.urban_or_rural_area_label, d.speed_limit,
       CASE WHEN d.first_road_number > 0 AND d.first_road_class BETWEEN 1 AND 4
            THEN CASE d.first_road_class WHEN 1 THEN 'M' WHEN 2 THEN 'A' WHEN 3 THEN 'A'
                                         ELSE 'B' END
                 || d.first_road_number
                 || CASE WHEN d.first_road_class = 2 THEN '(M)' ELSE '' END
            ELSE coalesce(d.first_road_class_label, 'Unclassified') END AS road,
       d.number_of_vehicles, d.number_of_casualties,
       ST_X(d.geom_wgs84) AS lon, ST_Y(d.geom_wgs84) AS lat
FROM mart.collision_decoded d
WHERE d.collision_index = ANY(%(ids)s)
ORDER BY d.collision_date, d.collision_time NULLS LAST, d.collision_index
"""

_VEHICLE = """
SELECT v.collision_index, v.vehicle_reference,
       v.vehicle_type, v.vehicle_type_label, v.road_user_group,
       v.vehicle_manoeuvre, v.vehicle_manoeuvre_label,
       v.vehicle_manoeuvre_historic, v.vehicle_manoeuvre_historic_label,
       v.first_point_of_impact, v.first_point_of_impact_label,
       v.skidding_and_overturning, v.skidding_and_overturning_label,
       v.vehicle_leaving_carriageway, v.vehicle_leaving_carriageway_label,
       v.hit_object_in_carriageway, v.hit_object_in_carriageway_label,
       v.hit_object_off_carriageway, v.hit_object_off_carriageway_label,
       v.junction_location_label,
       v.sex_of_driver_label, v.age_of_driver, v.age_band_of_driver_label
FROM mart.vehicle_decoded v
WHERE v.collision_index = ANY(%(ids)s)
ORDER BY v.collision_index, v.vehicle_reference
"""

_CASUALTY = """
SELECT k.collision_index, k.casualty_reference, k.casualty_seq, k.vehicle_reference,
       k.casualty_class, k.casualty_class_label,
       k.casualty_severity, k.age_of_casualty, k.age_band_of_casualty_label,
       k.sex_of_casualty_label, k.road_user_group,
       k.pedestrian_location_label, k.pedestrian_movement_label
FROM mart.casualty_decoded k
WHERE k.collision_index = ANY(%(ids)s)
ORDER BY k.collision_index, k.casualty_reference, k.casualty_seq
"""


def load_sticks(conn: psycopg.Connection, flt: Filter) -> dict:
    total = count_capped(conn, flt, MAX_STICKS)
    if total > MAX_STICKS:
        raise ApiError(
            413,
            "too_large",
            f"Stick diagrams cover up to {MAX_STICKS:,} collisions. "
            "Narrow the area, period or filters.",
        )
    ids = selected_ids(conn, flt)
    params = {"ids": ids}
    sticks = conn.execute(_COLLISION, params).fetchall()
    by_id = {s["collision_index"]: {**s, "vehicles": [], "casualties": []} for s in sticks}
    for v in conn.execute(_VEHICLE, params):
        by_id[v.pop("collision_index")]["vehicles"].append(v)
    for k in conn.execute(_CASUALTY, params):
        by_id[k.pop("collision_index")]["casualties"].append(k)
    return {"total": len(ids), "sticks": [by_id[s["collision_index"]] for s in sticks]}


@router.get("/sticks")
def sticks(conn: Conn, flt: Flt) -> dict:
    return ok(load_sticks(conn, flt))
