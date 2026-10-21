-- File: dim_lookup_test.sql
-- Description: Testing of the dim_lookup for functionality against the three tables
-- Author: Ben Wallbridge
-- Date: 2025-03-22

-- count total rows of dim_lookup
SELECT COUNT(*) AS total_rows FROM public.dim_lookup;

-- test to check lookup values tie with pedestrian location field
SELECT 
    c.accident_index,
    d.return_value AS pedestrian_location_description
FROM staging_casualty.casualty_data c
LEFT JOIN lookup.pedestrian_location_lookup d
    ON c.pedestrian_location::VARCHAR = d.lookup_key
LIMIT 100;

-- aggregate ccasualties by seriousness, with dim_lookup value
SELECT 
    c.accident_year,
    d.return_value AS casualty_severity_description,
    COUNT(*) AS count
FROM staging_casualty.casualty_data c
LEFT JOIN lookup.casualty_severity_lookup d
    ON c.casualty_severity::VARCHAR = d.lookup_key
GROUP BY c.accident_year, d.return_value
ORDER BY casualty_severity_description, d.return_value;