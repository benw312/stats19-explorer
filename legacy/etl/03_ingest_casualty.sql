-- ========================================================
-- 03_ingest_casualty.sql
-- Populate Production Casualties Table from Staging Data
-- ========================================================

INSERT INTO prod_casualties (
    accident_index,
    accident_year,
    accident_reference,
    vehicle_reference,
    casualty_reference,
    casualty_class,
    sex_of_casualty,
    age_of_casualty,
    age_band_of_casualty,
    casualty_severity,
    pedestrian_location,
    pedestrian_movement,
    car_passenger,
    bus_or_coach_passenger,
    pedestrian_road_maintenance_worker,
    casualty_type,
    casualty_home_area_type,
    casualty_imd_decile,
    lsoa_of_casualty,
    enhanced_casualty_severity,
    casualty_distance_banding
)
SELECT 
    accident_index,
    accident_year,
    accident_reference,
    vehicle_reference,
    casualty_reference,
    casualty_class,
    sex_of_casualty,
    age_of_casualty,
    age_band_of_casualty,
    casualty_severity,
    pedestrian_location,
    pedestrian_movement,
    car_passenger,
    bus_or_coach_passenger,
    pedestrian_road_maintenance_worker,
    casualty_type,
    casualty_home_area_type,
    casualty_imd_decile,
    lsoa_of_casualty,
    enhanced_casualty_severity,
    casualty_distance_banding
FROM staging_casualty.casualty_data;