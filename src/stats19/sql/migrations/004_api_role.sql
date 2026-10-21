-- PLAN-006 C4: a read-only role for the API, so a compromised API process can't change data.
-- It can read every schema the pipeline owns; default privileges keep tables the pipeline
-- rebuilds (and schemas it swaps in, e.g. mart) readable. LOGIN and its password are set
-- by `stats19 migrate` from STATS19_API_DB_PASSWORD (db.ensure_api_role), not stored here.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'stats19_api') THEN
        CREATE ROLE stats19_api NOLOGIN;
    END IF;
END $$;

ALTER ROLE stats19_api SET statement_timeout = '60s';
ALTER ROLE stats19_api SET default_transaction_read_only = on;

DO $$
DECLARE
    s text;
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO stats19_api', current_database());
    FOR s IN SELECT nspname FROM pg_namespace
             WHERE nspname IN ('core', 'mart', 'geo', 'etl', 'raw', 'build') LOOP
        EXECUTE format('GRANT USAGE ON SCHEMA %I TO stats19_api', s);
        EXECUTE format('GRANT SELECT ON ALL TABLES IN SCHEMA %I TO stats19_api', s);
    END LOOP;
    -- objects the owner creates later, in any schema (rebuilt tables, swapped schemas)
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I GRANT SELECT ON TABLES TO stats19_api',
                   current_user);
    EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE %I GRANT USAGE ON SCHEMAS TO stats19_api',
                   current_user);
END $$;
