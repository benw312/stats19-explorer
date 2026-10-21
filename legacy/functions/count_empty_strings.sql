-- File: count_empty_strings.sql
-- Description: dynamically counts empty string values ('') in all text-based columns (VARCHAR, TEXT) of a specified table and returns a summary showing how many empty strings are in each of those columns.
-- Author: Ben Wallbridge
-- Date: 2025-03-22

-- example: SELECT * FROM count_empty_strings('staging_casualty', 'casualty_data');

CREATE OR REPLACE FUNCTION public.count_empty_strings(p_schema_name text, p_table_name text)
 RETURNS TABLE(column_name text, empty_count bigint)
 LANGUAGE plpgsql
AS $function$
DECLARE 
    col_name TEXT;
    query TEXT;
BEGIN
    -- Start building query
    query := 'SELECT unnest(array[';

    -- Loop through text columns dynamically
    FOR col_name IN 
        SELECT c.column_name 
        FROM information_schema.columns c
        WHERE c.table_schema = p_schema_name 
          AND c.table_name = p_table_name
          AND c.data_type IN ('character varying', 'text')  -- Only check text fields
    LOOP
        query := query || quote_literal(col_name) || ', ';
    END LOOP;

    -- Trim last comma, close array
    query := RTRIM(query, ', ') || ']) AS column_name, unnest(array[';

    -- Append empty string counts dynamically
    FOR col_name IN 
        SELECT c.column_name 
        FROM information_schema.columns c
        WHERE c.table_schema = p_schema_name 
          AND c.table_name = p_table_name
          AND c.data_type IN ('character varying', 'text')
    LOOP
        query := query || 'SUM(CASE WHEN ' || quote_ident(col_name) || ' = '''' THEN 1 ELSE 0 END), ';
    END LOOP;

    -- Trim last comma and close array
    query := RTRIM(query, ', ') || ']) AS empty_count FROM ' || quote_ident(p_schema_name) || '.' || quote_ident(p_table_name) || ';';

    -- Execute the dynamically built query
    RETURN QUERY EXECUTE query;
END $function$
;
