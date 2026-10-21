-- FU-052: "what's near this point" (/api/sites/near) searches junctions and count point
-- stretches by distance in BNG; without these it scanned every junction (~1M rows).
-- The junction and traffic link builds recreate them whenever they rebuild the tables.
DO $$
BEGIN
    IF to_regclass('geo.junction') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS junction_geom_bng_idx ON geo.junction USING gist (geom_bng);
    END IF;
    IF to_regclass('geo.traffic_stretch') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS traffic_stretch_geom_bng_idx
            ON geo.traffic_stretch USING gist (geom_bng);
    END IF;
END $$;
