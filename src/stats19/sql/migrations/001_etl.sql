-- 001_etl.sql — extensions, ETL bookkeeping and safe type-conversion helpers.

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS etl;
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS etl.run (
    run_id             bigserial PRIMARY KEY,
    started_at         timestamptz NOT NULL DEFAULT now(),
    finished_at        timestamptz,
    status             text NOT NULL DEFAULT 'running'
                       CHECK (status IN ('running', 'success', 'failed', 'skipped')),
    source_updated_at  text,
    message            text
);

CREATE TABLE IF NOT EXISTS etl.source_file (
    run_id             bigint NOT NULL REFERENCES etl.run (run_id),
    table_name         text NOT NULL,
    url                text,
    sha256             text NOT NULL,
    size_bytes         bigint NOT NULL,
    raw_row_count      bigint,
    header_missing     text[] NOT NULL DEFAULT '{}',
    header_unexpected  text[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (run_id, table_name)
);

CREATE TABLE IF NOT EXISTS etl.run_check (
    run_id      bigint NOT NULL REFERENCES etl.run (run_id),
    check_name  text NOT NULL,
    table_name  text NOT NULL DEFAULT '',
    severity    text NOT NULL CHECK (severity IN ('error', 'warn', 'info')),
    passed      boolean NOT NULL,
    observed    numeric,
    threshold   numeric,
    detail      text,
    PRIMARY KEY (run_id, check_name, table_name)
);

-- Conversions return NULL for blank or unparseable input instead of aborting
-- a multi-million-row load; validate.py counts how often that happens.

CREATE OR REPLACE FUNCTION etl.to_int(v text) RETURNS integer
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN pg_input_is_valid(btrim(v), 'integer') THEN btrim(v)::integer END
$$;

CREATE OR REPLACE FUNCTION etl.to_code(v text) RETURNS smallint
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN pg_input_is_valid(btrim(v), 'smallint') THEN btrim(v)::smallint END
$$;

-- Measures (ages, engine size, coordinates, road numbers) use -1 for "missing".
CREATE OR REPLACE FUNCTION etl.to_measure(v text) RETURNS integer
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT NULLIF(etl.to_int(v), -1)
$$;

CREATE OR REPLACE FUNCTION etl.to_float(v text) RETURNS double precision
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN pg_input_is_valid(btrim(v), 'double precision')
                THEN btrim(v)::double precision END
$$;

-- Source dates are DD/MM/YYYY.
CREATE OR REPLACE FUNCTION etl.to_date_dmy(v text) RETURNS date
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN btrim(v) ~ '^\d{2}/\d{2}/\d{4}$'
         AND pg_input_is_valid(
                substr(btrim(v), 7, 4) || '-' || substr(btrim(v), 4, 2) || '-' || substr(btrim(v), 1, 2),
                'date')
        THEN (substr(btrim(v), 7, 4) || '-' || substr(btrim(v), 4, 2) || '-' || substr(btrim(v), 1, 2))::date
    END
$$;

CREATE OR REPLACE FUNCTION etl.to_hhmm(v text) RETURNS time
LANGUAGE sql STABLE PARALLEL SAFE AS $$
    SELECT CASE WHEN btrim(v) ~ '^\d{1,2}:\d{2}(:\d{2})?$' AND pg_input_is_valid(btrim(v), 'time')
                THEN btrim(v)::time END
$$;
