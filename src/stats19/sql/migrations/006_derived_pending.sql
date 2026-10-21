-- FU-051: derived builds (traffic links, junctions, matches, safety, authorities) asked for
-- but not yet finished. A row is added when a loader asks for a build and removed when the
-- build commits, so a failed build is retried at the pipeline's next check.
CREATE TABLE IF NOT EXISTS etl.derived_pending (
    step          text PRIMARY KEY,
    requested_at  timestamptz NOT NULL DEFAULT now()
);
