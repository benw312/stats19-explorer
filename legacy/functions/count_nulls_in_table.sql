-- File: count_nulls_in_table.sql
-- Author: Ben Wallbridge
-- Date: 2025-03-22

/*
===============================================================================
Function:     count_nulls_in_table(p_schema_name TEXT, p_table_name TEXT)
Returns:      TABLE (column_name TEXT, null_count BIGINT)
Language:     PL/pgSQL
-------------------------------------------------------------------------------
Description:
    Dynamically counts the number of NULL values in each column of a given table.

    This function queries the PostgreSQL information schema to find all columns
    in the specified schema and table, then builds and executes a dynamic SQL 
    query that counts NULLs for each column individually.

-------------------------------------------------------------------------------
Example Usage:
    SELECT * FROM count_nulls_in_table('staging_casualty', 'casualty_data');

-------------------------------------------------------------------------------
Example Output:
    column_name           | null_count
    ----------------------+------------
    accident_index        | 0
    age_of_driver         | 48
    lsoa_of_driver        | 10

-------------------------------------------------------------------------------
Why Use This:
    - Quickly profile the quality of your dataset
    - Identify missing data patterns across wide tables
    - Useful for validation and cleaning during ETL
===============================================================================
*/

CREATE OR REPLACE FUNCTION public.count_nulls_in_table(p_schema_name text, p_table_name text)
 RETURNS TABLE(column_name text, null_count bigint)
 LANGUAGE plpgsql
AS $function$
DECLARE 
    col_name TEXT;
    query TEXT;
BEGIN
    -- Start building the dynamic SQL query
    query := 'SELECT unnest(array[';

    -- Loop through each column in the given table
    FOR col_name IN 
        SELECT c.column_name 
        FROM information_schema.columns c
        WHERE c.table_schema = p_schema_name 
          AND c.table_name = p_table_name
    LOOP
        query := query || quote_literal(col_name) || ', ';
    END LOOP;

    -- Trim last comma and close array
    query := RTRIM(query, ', ') || ']) AS column_name, unnest(array[';

    -- Append NULL counts dynamically
    FOR col_name IN 
        SELECT c.column_name 
        FROM information_schema.columns c
        WHERE c.table_schema = p_schema_name 
          AND c.table_name = p_table_name
    LOOP
        query := query || 'SUM(CASE WHEN ' || quote_ident(col_name) || ' IS NULL THEN 1 ELSE 0 END), ';
    END LOOP;

    -- Trim last comma and close array
    query := RTRIM(query, ', ') || ']) AS null_count FROM ' || quote_ident(p_schema_name) || '.' || quote_ident(p_table_name) || ';';

    -- Execute the dynamically built query
    RETURN QUERY EXECUTE query;
END $function$
;