-- core.sql — turn build.*_typed into keyed, spatially enabled tables.
--
-- Runs inside schema "build", which becomes "core" after validation.
-- Expects build.collision_typed / vehicle_typed / casualty_typed (exact duplicate
-- rows already collapsed). Rows that can't satisfy the keys go to build.quarantine
-- with a reason, so constraints can be added without failing the load.

CREATE TABLE build.quarantine (
    table_name       text NOT NULL,
    reason           text NOT NULL,
    collision_index  text,
    record           jsonb NOT NULL
);

-- ---------------------------------------------------------------- collision

CREATE UNLOGGED TABLE build.collision_dupkey AS
SELECT collision_index FROM build.collision_typed
WHERE collision_index IS NOT NULL
GROUP BY collision_index HAVING count(*) > 1;

INSERT INTO build.quarantine
SELECT 'collision',
       CASE WHEN t.collision_index IS NULL THEN 'null_key' ELSE 'conflicting_duplicate_key' END,
       t.collision_index, to_jsonb(t)
FROM build.collision_typed t
WHERE t.collision_index IS NULL
   OR t.collision_index IN (SELECT collision_index FROM build.collision_dupkey);

CREATE TABLE build.collision AS
SELECT t.*,
       (t.date + t.time)::timestamp AS collision_datetime,
       CASE WHEN t.location_easting_osgr BETWEEN 1 AND 700000
             AND t.location_northing_osgr BETWEEN 1 AND 1300000
            THEN ST_SetSRID(ST_MakePoint(t.location_easting_osgr, t.location_northing_osgr), 27700)
       END::geometry(Point, 27700) AS geom_bng
FROM build.collision_typed t
WHERE t.collision_index IS NOT NULL
  AND t.collision_index NOT IN (SELECT collision_index FROM build.collision_dupkey);

-- WGS84 point: published lon/lat where present, else transformed from BNG (pre-1999 rows).
-- geom_3857 (Web Mercator) is stored for map tiles so they never re-project per request.
ALTER TABLE build.collision
    ADD COLUMN geom_wgs84 geometry(Point, 4326),
    ADD COLUMN geom_3857 geometry(Point, 3857);
UPDATE build.collision SET geom_wgs84 = g, geom_3857 = ST_Transform(g, 3857)
FROM (
    SELECT collision_index,
           CASE WHEN longitude BETWEEN -9 AND 3 AND latitude BETWEEN 49 AND 61.5
                THEN ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
                WHEN geom_bng IS NOT NULL
                THEN ST_Transform(geom_bng, 4326)
           END AS g
    FROM build.collision
) w
WHERE w.collision_index = build.collision.collision_index;

ALTER TABLE build.collision RENAME COLUMN date TO collision_date;
ALTER TABLE build.collision RENAME COLUMN time TO collision_time;
ALTER TABLE build.collision ADD PRIMARY KEY (collision_index);

-- ---------------------------------------------------------------- vehicle

CREATE UNLOGGED TABLE build.vehicle_dupkey AS
SELECT collision_index, vehicle_reference FROM build.vehicle_typed
WHERE collision_index IS NOT NULL AND vehicle_reference IS NOT NULL
GROUP BY 1, 2 HAVING count(*) > 1;

INSERT INTO build.quarantine
SELECT 'vehicle',
       CASE WHEN t.collision_index IS NULL OR t.vehicle_reference IS NULL THEN 'null_key'
            WHEN d.collision_index IS NOT NULL THEN 'conflicting_duplicate_key'
            ELSE 'orphan_collision' END,
       t.collision_index, to_jsonb(t)
FROM build.vehicle_typed t
LEFT JOIN build.vehicle_dupkey d USING (collision_index, vehicle_reference)
LEFT JOIN build.collision c USING (collision_index)
WHERE t.collision_index IS NULL OR t.vehicle_reference IS NULL
   OR d.collision_index IS NOT NULL
   OR c.collision_index IS NULL;

CREATE TABLE build.vehicle AS
SELECT t.*
FROM build.vehicle_typed t
JOIN build.collision c USING (collision_index)
LEFT JOIN build.vehicle_dupkey d USING (collision_index, vehicle_reference)
WHERE t.vehicle_reference IS NOT NULL AND d.collision_index IS NULL;

ALTER TABLE build.vehicle ADD PRIMARY KEY (collision_index, vehicle_reference);

-- ---------------------------------------------------------------- casualty

INSERT INTO build.quarantine
SELECT 'casualty',
       CASE WHEN t.collision_index IS NULL OR t.casualty_reference IS NULL THEN 'null_key'
            ELSE 'orphan_collision' END,
       t.collision_index, to_jsonb(t)
FROM build.casualty_typed t
LEFT JOIN build.collision c USING (collision_index)
WHERE t.collision_index IS NULL OR t.casualty_reference IS NULL
   OR c.collision_index IS NULL;

-- A casualty whose vehicle_reference matches no vehicle is kept (casualty counts
-- matter more than the link) with vehicle_reference set NULL; the original row is
-- recorded in quarantine with reason 'orphan_vehicle_unlinked'.
INSERT INTO build.quarantine
SELECT 'casualty', 'orphan_vehicle_unlinked', t.collision_index, to_jsonb(t)
FROM build.casualty_typed t
JOIN build.collision c USING (collision_index)
LEFT JOIN build.vehicle v USING (collision_index, vehicle_reference)
WHERE t.casualty_reference IS NOT NULL
  AND t.vehicle_reference IS NOT NULL
  AND v.collision_index IS NULL;

-- Some records (mostly 1991-94) reuse a casualty_reference for different casualties
-- in the same collision (FU-008). They're real people, so all are kept. casualty_seq
-- numbers them deterministically (by vehicle, then full row) so keys are stable
-- between releases; it is 1 for every normal casualty.
CREATE TABLE build.casualty AS
SELECT t.*,
       (row_number() OVER w)::smallint AS casualty_seq,
       (count(*) OVER (PARTITION BY t.collision_index, t.casualty_reference) > 1)
           AS is_reference_reused
FROM build.casualty_typed t
JOIN build.collision c USING (collision_index)
WHERE t.casualty_reference IS NOT NULL
WINDOW w AS (PARTITION BY t.collision_index, t.casualty_reference
             ORDER BY t.vehicle_reference NULLS LAST, to_jsonb(t)::text);

UPDATE build.casualty k SET vehicle_reference = NULL
WHERE vehicle_reference IS NOT NULL
  AND NOT EXISTS (
      SELECT 1 FROM build.vehicle v
      WHERE v.collision_index = k.collision_index AND v.vehicle_reference = k.vehicle_reference);

ALTER TABLE build.casualty ADD PRIMARY KEY (collision_index, casualty_reference, casualty_seq);

-- ---------------------------------------------------------------- foreign keys

ALTER TABLE build.vehicle
    ADD CONSTRAINT vehicle_collision_fk
    FOREIGN KEY (collision_index) REFERENCES build.collision (collision_index);
ALTER TABLE build.casualty
    ADD CONSTRAINT casualty_collision_fk
    FOREIGN KEY (collision_index) REFERENCES build.collision (collision_index);
ALTER TABLE build.casualty
    ADD CONSTRAINT casualty_vehicle_fk
    FOREIGN KEY (collision_index, vehicle_reference)
    REFERENCES build.vehicle (collision_index, vehicle_reference);

-- ---------------------------------------------------------------- indexes

CREATE INDEX collision_date_idx       ON build.collision (collision_date);
CREATE INDEX collision_year_idx       ON build.collision (collision_year);
CREATE INDEX collision_severity_idx   ON build.collision (collision_severity);
CREATE INDEX collision_police_idx     ON build.collision (police_force);
CREATE INDEX collision_la_ons_idx     ON build.collision (local_authority_ons_district);
CREATE INDEX collision_geom_bng_idx   ON build.collision USING gist (geom_bng);
CREATE INDEX collision_geom_wgs84_idx ON build.collision USING gist (geom_wgs84);
CREATE INDEX collision_geom_3857_idx  ON build.collision USING gist (geom_3857);
CREATE INDEX casualty_vehicle_idx     ON build.casualty (collision_index, vehicle_reference);
CREATE INDEX quarantine_table_idx     ON build.quarantine (table_name, reason);

-- ---------------------------------------------------------------- tidy up

DROP TABLE build.collision_dupkey, build.vehicle_dupkey;

COMMENT ON TABLE build.collision IS 'STATS19 collisions, one row per collision_index';
COMMENT ON TABLE build.vehicle   IS 'STATS19 vehicles, PK (collision_index, vehicle_reference)';
COMMENT ON TABLE build.casualty  IS 'STATS19 casualties, PK (collision_index, casualty_reference, casualty_seq)';
COMMENT ON COLUMN build.casualty.casualty_seq IS
    '1 for normal rows; numbers casualties that share a casualty_reference (see is_reference_reused)';
COMMENT ON TABLE build.quarantine IS 'Source rows rejected or altered to satisfy keys, with reason';
COMMENT ON COLUMN build.casualty.vehicle_reference IS
    'NULL where the published vehicle_reference matched no vehicle (see quarantine)';
