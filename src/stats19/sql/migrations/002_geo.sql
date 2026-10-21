-- 002_geo.sql — reference data for search, areas and costing (PLAN-004).
-- Tables are (re)created by stats19.reference loaders, which swap in a fresh copy;
-- this migration only sets up the schema, extensions and the refresh log.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS geo;

CREATE TABLE IF NOT EXISTS geo.reference_refresh (
    dataset       text PRIMARY KEY,
    refreshed_at  timestamptz NOT NULL DEFAULT now(),
    source        text NOT NULL,
    row_count     bigint NOT NULL,
    detail        text
);
