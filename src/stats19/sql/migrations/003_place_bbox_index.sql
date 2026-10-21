-- PLAN-005: label cluster sites with the nearest named road (geo.place bboxes).
-- The reference refresh recreates this index whenever it rebuilds geo.place.
DO $$
BEGIN
    IF to_regclass('geo.place') IS NOT NULL THEN
        CREATE INDEX IF NOT EXISTS place_bbox_idx ON geo.place USING gist (bbox_bng);
    END IF;
END $$;
