-- PLAN-011 S1: the app schema, the first data that can't be rebuilt from public sources.
-- The pipeline never touches it; it's backed up daily (docker/backup.sh).
--
-- Organisation-aware from the start (PLAN-014 D5): every table carries org_id. Until accounts
-- exist (PLAN-014 C2) there is one organisation, and stats19.api.org.current_org returns it.
CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.org (
    id          uuid PRIMARY KEY,
    name        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);

INSERT INTO app.org (id, name)
VALUES ('00000000-0000-0000-0000-000000000001', 'Default')
ON CONFLICT (id) DO NOTHING;

-- A road safety scheme at a site, with a snapshot of the site's footprint so its evaluation
-- never moves when the pipeline rebuilds junctions or clusters (PLAN-011 §2). The measure
-- list lives in stats19.api.schemes, so it can grow without a migration.
CREATE TABLE IF NOT EXISTS app.scheme (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id        uuid NOT NULL REFERENCES app.org (id),
    name          text NOT NULL CHECK (length(name) BETWEEN 1 AND 200),
    description   text NOT NULL DEFAULT '' CHECK (length(description) <= 5000),
    measure       text NOT NULL CHECK (length(measure) BETWEEN 1 AND 40),
    site_type     text NOT NULL
                  CHECK (site_type IN ('junction', 'link', 'cluster', 'route', 'area')),
    site_ref      text CHECK (length(site_ref) <= 200),
    geom_bng      geometry(Geometry, 27700) NOT NULL CHECK (ST_IsValid(geom_bng)),
    works_start   date,
    works_end     date CHECK (works_end >= works_start),
    before_years  smallint NOT NULL DEFAULT 3 CHECK (before_years BETWEEN 1 AND 5),
    after_years   smallint NOT NULL DEFAULT 3 CHECK (after_years BETWEEN 1 AND 5),
    cost          numeric(14, 2) CHECK (cost >= 0),
    fyrr          jsonb,
    -- optimistic locking: an edit must name the version it started from
    version       integer NOT NULL DEFAULT 1,
    created_at    timestamptz NOT NULL DEFAULT now(),
    created_by    text NOT NULL,
    updated_at    timestamptz NOT NULL DEFAULT now(),
    updated_by    text NOT NULL,
    -- deleting only marks the row, so a mistake can be undone from SQL
    deleted_at    timestamptz,
    deleted_by    text
);

CREATE UNIQUE INDEX IF NOT EXISTS scheme_org_name_idx
    ON app.scheme (org_id, lower(name)) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS scheme_geom_bng_idx ON app.scheme USING gist (geom_bng);

-- The API's role stays read-only by default (004). On app it may add and edit schemes, and
-- only the columns an edit can change: never id, org_id or the created_* stamp. No DELETE:
-- deleting is an UPDATE of deleted_at.
GRANT USAGE ON SCHEMA app TO stats19_api;
GRANT SELECT ON ALL TABLES IN SCHEMA app TO stats19_api;
GRANT INSERT ON app.scheme TO stats19_api;
GRANT UPDATE (name, description, measure, site_type, site_ref, geom_bng, works_start,
              works_end, before_years, after_years, cost, fyrr, version, updated_at,
              updated_by, deleted_at, deleted_by)
    ON app.scheme TO stats19_api;
