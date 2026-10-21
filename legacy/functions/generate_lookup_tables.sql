-- File: generate_lookup_tables.sql
-- Author: Ben Wallbridge
-- Date: 2025-03-22

/*
===============================================================================
Function:     generate_lookup_tables()
Returns:      VOID
Language:     PL/pgSQL
-------------------------------------------------------------------------------
Description:
    Dynamically creates a set of lookup tables from the central `dim_lookup` table.

    For each unique `field_name` in `public.dim_lookup`, this function:
    - Creates a new table in the `lookup` schema with the name:
        lookup.{field_name}_lookup
    - Each table contains:
        - `lookup_key` (VARCHAR) as the PRIMARY KEY
        - `return_value` (VARCHAR) as the human-readable label
    - Inserts values from `dim_lookup` into the corresponding table
    - Skips any lookup values that already exist (uses `ON CONFLICT DO NOTHING`)

    Table names are automatically sanitised by replacing spaces with underscores
    and appending `_lookup`.

-------------------------------------------------------------------------------
Example Usage:
    SELECT generate_lookup_tables();

-------------------------------------------------------------------------------
Example Output:
    Creates multiple tables such as:
        - lookup.casualty_severity_lookup
        - lookup.junction_detail_lookup
        - lookup.sex_of_driver_lookup

-------------------------------------------------------------------------------
Why Use This:
    - Automates normalisation of encoded categorical data
    - Keeps lookup values consistent and queryable
    - Enables fast LEFT JOINs for decoding integer fields into readable labels
    - Prevents duplication by using INSERT ... ON CONFLICT

===============================================================================
*/

CREATE OR REPLACE FUNCTION public.generate_lookup_tables()
 RETURNS void
 LANGUAGE plpgsql
AS $function$
DECLARE 
    field TEXT;
    table_name TEXT;
BEGIN
    -- Ensure the lookup schema exists
    CREATE SCHEMA IF NOT EXISTS lookup;

    -- Loop through each unique field_name in dim_lookup
    FOR field IN (SELECT DISTINCT field_name FROM public.dim_lookup) 
    LOOP
        -- Build the table name by replacing spaces with underscores and appending _lookup
        table_name := replace(field, ' ', '_') || '_lookup';

        -- Create the lookup table dynamically inside the 'lookup' schema
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS lookup.%I (
                lookup_key VARCHAR(12) PRIMARY KEY,
                return_value VARCHAR(150)
            );', table_name);

        -- Insert the relevant lookup values from dim_lookup
        EXECUTE format('
            INSERT INTO lookup.%I (lookup_key, return_value)
            SELECT lookup_key, return_value 
            FROM public.dim_lookup 
            WHERE field_name = %L
            ON CONFLICT (lookup_key) DO NOTHING;', table_name, field);
    END LOOP;
END $function$
;