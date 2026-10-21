-- File: initial_eda.sql
-- Description: initial EDA of the three tables, casualty, collision and vehicle
-- Author: Ben Wallbridge
-- Date: 2025-03-22

-- check total rows from all three tables
SELECT COUNT(*) AS total_rows FROM staging_casualty.casualty_data;
SELECT COUNT(*) AS total_rows FROM staging_collision.collision_data;
SELECT COUNT(*) AS total_rows FROM staging_vehicles.vehicle_data;

-- For casualty data by year
SELECT accident_year, COUNT(*) AS total
FROM staging_casualty.casualty_data
GROUP BY accident_year
ORDER BY accident_year;

-- Check for nulls in casualty_data for accident_index and accident_year
SELECT COUNT(*) AS null_count
FROM staging_casualty.casualty_data
WHERE accident_index IS NULL OR accident_year IS NULL;

-- check min and max of engine size
SELECT MIN(engine_capacity_cc) AS min_engine, 
       MAX(engine_capacity_cc) AS max_engine
FROM staging_vehicles.vehicle_data;

-- eda of ages in vehicle data table
SELECT 
    COUNT(*) AS total_rows,
    AVG(age_of_driver) AS avg_age,
    MIN(age_of_driver) AS min_age,
    MAX(age_of_driver) AS max_age,
    STDDEV(age_of_driver) AS stddev_age
FROM staging_vehicles.vehicle_data;

-- check for nulls in accident index of casualty data
select count(*) as null_count
from staging_casualty.casualty_data cd 
where cd.accident_index is null;

-- check for nulls in accident index of collision data
select count(*) as null_count
from staging_collision.collision_data cd 
where cd.accident_index is null;

-- check for nulls in accident index of vehicle data
select count(*) as null_count
from staging_vehicles.vehicle_data cd 
where cd.accident_index is null;

-- count null values from casualty data
SELECT * FROM count_nulls_in_table('staging_casualty', 'casualty_data');

-- count null values from collision data
SELECT * FROM count_nulls_in_table('staging_collision', 'collision_data');

-- count null values from vehicle data
SELECT * FROM count_nulls_in_table('staging_vehicles', 'vehicle_data');

-- count empty strings from casualty data using stored function
SELECT * FROM count_empty_strings('staging_casualty', 'casualty_data');

-- count empty strings from collision data using stored function
SELECT * FROM count_empty_strings('staging_collision', 'collision_data');

-- count empty strings from vehicle data using stored function
SELECT * FROM count_empty_strings('staging_vehicles', 'vehicle_data');

-- count unique values casualty data using stored function
SELECT * FROM count_unique_values('staging_casualty', 'casualty_data');

-- count unique values collision data using stored function
SELECT * FROM count_unique_values('staging_collision', 'collision_data');

-- count unique values vehicle data using stored function
SELECT * FROM count_unique_values('staging_vehicles', 'vehicle_data');

SELECT accident_index, COUNT(*)
FROM staging_collision.collision_data
GROUP BY accident_index
HAVING COUNT(*) > 1;

SELECT c.accident_index,
       COUNT(DISTINCT cas.casualty_reference) AS casualty_count,
       COUNT(DISTINCT v.vehicle_reference) AS vehicle_count
FROM staging_collision.collision_data c
LEFT JOIN staging_casualty.casualty_data cas ON c.accident_index = cas.accident_index
LEFT JOIN staging_vehicles.vehicle_data v ON c.accident_index = v.accident_index
GROUP BY c.accident_index
ORDER BY casualty_count DESC, vehicle_count DESC
LIMIT 10;

-- check of highest casualties per single collision
SELECT *
FROM staging_casualty.casualty_data
WHERE accident_index = '2023520300610';

-- check for casualties without matching collision ref
SELECT cas.accident_index
FROM staging_casualty.casualty_data cas
LEFT JOIN staging_collision.collision_data col ON cas.accident_index = col.accident_index
WHERE col.accident_index IS NULL;

-- check for vehicles without matching collision ref
SELECT veh.accident_index
FROM staging_vehicles.vehicle_data veh
LEFT JOIN staging_collision.collision_data col ON veh.accident_index = col.accident_index
WHERE col.accident_index IS NULL;