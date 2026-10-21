-- File: count_unique_values.sql
-- Author: Ben Wallbridge
-- Date: 2025-03-22

/*
===============================================================================
Function:     count_unique_values(p_schema_name TEXT, p_table_name TEXT)
Returns:      TABLE (column_name TEXT, unique_count BIGINT)
Language:     PL/pgSQL
-------------------------------------------------------------------------------
Description:
    Dynamically counts the number of unique values in each column of a specified
    table within a given schema.

    This function uses PostgreSQL's information schema to identify all columns
    in the target table, and constructs a dynamic SQL query to return a list 
    of columns alongside their respective counts of distinct (non-null) values.

-------------------------------------------------------------------------------
Example Usage:
    SELECT * FROM count_unique_values('staging_casualty', 'casualty_data');

-------------------------------------------------------------------------------
Example Output:
    column_name           | unique_count
    ----------------------+--------------
    accident_index        | 520084
    casualty_severity     | 3
    sex_of_casualty       | 4

-------------------------------------------------------------------------------
Why Use This:
    - Quickly explore data variety and cardinality
    - Identify potential categorical vs. continuous fields
    - Detect data anomalies (e.g., excessive distinct values in categorical fields)
    - Supports profiling and validation stages of ETL workflows
===============================================================================
*/

CREATE OR REPLACE FUNCTION public.count_unique_values(p_schema_name text, p_table_name text)
 RETURNS TABLE(column_name text, unique_count bigint)
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

    -- Trim last comma, close array
    query := RTRIM(query, ', ') || ']) AS column_name, unnest(array[';

    -- Append unique value counts dynamically
    FOR col_name IN 
        SELECT c.column_name 
        FROM information_schema.columns c
        WHERE c.table_schema = p_schema_name 
          AND c.table_name = p_table_name
    LOOP
        query := query || '(SELECT COUNT(DISTINCT ' || quote_ident(col_name) || ') FROM ' || quote_ident(p_schema_name) || '.' || quote_ident(p_table_name) || '), ';
    END LOOP;

    -- Trim last comma and close array
    query := RTRIM(query, ', ') || ']) AS unique_count;';

    -- Execute the dynamically built query
    RETURN QUERY EXECUTE query;
END $function$
;