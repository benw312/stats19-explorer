-- File: collisions_location_checks.sql
-- Description: testing of the location data in collision table
-- Author: Ben Wallbridge
-- Date: 2025-03-22

-- check for location in the UK (lon and lat)
SELECT accident_index, longitude, latitude
FROM staging_collision.collision_data
WHERE latitude NOT BETWEEN 49.8 AND 60.9
   OR longitude NOT BETWEEN -8.6 AND 1.8;

-- check for location in the UK (osgr)
SELECT accident_index, location_easting_osgr, location_northing_osgr
FROM staging_collision.collision_data
WHERE location_easting_osgr NOT BETWEEN 0 AND 700000
   OR location_northing_osgr NOT BETWEEN 0 AND 1300000;

-- check for grouped locations
SELECT longitude, latitude, COUNT(*) AS occurrence_count
FROM staging_collision.collision_data
GROUP BY longitude, latitude
ORDER BY occurrence_count DESC
LIMIT 10;

-- check for exact same coords being used
SELECT longitude, latitude, COUNT(*) AS duplicate_count
FROM staging_collision.collision_data
GROUP BY longitude, latitude
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC;

-- inspect collisions with no coords
SELECT * 
FROM staging_collision.collision_data
WHERE (longitude IS NULL OR latitude IS NULL) 
AND (location_easting_osgr IS NULL OR location_northing_osgr IS NULL)
ORDER BY accident_year DESC, accident_index;