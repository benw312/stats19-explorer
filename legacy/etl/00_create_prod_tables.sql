-- ========================================================
-- 00_create_prod_tables.sql
-- Production tables for Stats19 Database
-- ========================================================

-- --------------------------
-- Table: collisions
-- --------------------------
CREATE TABLE prod_collisions (
    accident_index                 VARCHAR(20) NOT NULL,
    accident_year                  INT4,
    accident_reference             VARCHAR(20) NOT NULL,
    location_easting_osgr          INT4,
    location_northing_osgr         INT4,
    longitude                      FLOAT8,
    latitude                       FLOAT8,
    police_force                   INT4,
    accident_severity              INT4,
    number_of_vehicles             INT4,
    number_of_casualties           INT4,
    date                           TEXT,
    day_of_week                    INT4,
    time                           TIME,
    local_authority_district       INT4,
    local_authority_ons_district   VARCHAR(20),
    local_authority_highway        VARCHAR(20),
    first_road_class               INT4,
    first_road_number              INT4,
    road_type                      INT4,
    speed_limit                    INT4,
    junction_detail                INT4,
    junction_control               INT4,
    second_road_class              INT4,
    second_road_number             INT4,
    pedestrian_crossing_human_control INT4,
    pedestrian_crossing_physical_facilities INT4,
    light_conditions               INT4,
    weather_conditions             INT4,
    road_surface_conditions        INT4,
    special_conditions_at_site     INT4,
    carriageway_hazards            INT4,
    urban_or_rural_area            INT4,
    did_police_officer_attend_scene_of_accident INT4,
    trunk_road_flag                INT4,
    lsoa_of_accident_location      VARCHAR(20),
    enhanced_severity_collision    INT4,
    
    CONSTRAINT pk_prod_collisions PRIMARY KEY (accident_index)
);

-- --------------------------
-- Table: vehicles (Production)
-- --------------------------
CREATE TABLE prod_vehicles (
    accident_index                    VARCHAR(20) NOT NULL,
    accident_year                     INT4,
    accident_reference                VARCHAR(20) NOT NULL,
    vehicle_reference                 INT4,
    vehicle_type                      INT4,
    towing_and_articulation           INT4,
    vehicle_manoeuvre                 INT4,
    vehicle_direction_from            INT4,
    vehicle_direction_to              INT4,
    vehicle_location_restricted_lane  INT4,
    junction_location                 INT4,
    skidding_and_overturning          INT4,
    hit_object_in_carriageway         INT4,
    vehicle_leaving_carriageway       INT4,
    hit_object_off_carriageway        INT4,
    first_point_of_impact             INT4,
    vehicle_left_hand_drive           INT4,
    journey_purpose_of_driver         INT4,
    sex_of_driver                     INT4,
    age_of_driver                     INT4,
    age_band_of_driver                INT4,
    engine_capacity_cc                INT4,
    propulsion_code                   INT4,
    age_of_vehicle                    INT4,
    generic_make_model                VARCHAR(100),
    driver_imd_decile                 INT4,
    driver_home_area_type             INT4,
    lsoa_of_driver                    VARCHAR(20),
    escooter_flag                     INT4,
    dir_from_e                        INT4,
    dir_from_n                        INT4,
    dir_to_e                          INT4,
    dir_to_n                          INT4,
    driver_distance_banding           INT4,
    
    -- New unique reference computed from accident_index and vehicle_reference
    vehicle_unique_ref                VARCHAR(60) GENERATED ALWAYS AS (accident_index || vehicle_reference::text) STORED,
    
    CONSTRAINT pk_prod_vehicles PRIMARY KEY (vehicle_unique_ref),
    CONSTRAINT fk_prod_vehicles_collisions FOREIGN KEY (accident_index)
        REFERENCES prod_collisions(accident_index)
);

-- --------------------------
-- Table: casualties
-- --------------------------
CREATE TABLE prod_casualties (
    accident_index            VARCHAR(20) NOT NULL,
    accident_year             INT4,
    accident_reference        VARCHAR(20) NOT NULL,
    vehicle_reference         INT4,
    casualty_reference        INT4,
    casualty_class            INT4,
    sex_of_casualty           INT4,
    age_of_casualty           INT4,
    age_band_of_casualty      INT4,
    casualty_severity         INT4,
    pedestrian_location       INT4,
    pedestrian_movement       INT4,
    car_passenger             INT4,
    bus_or_coach_passenger    INT4,
    pedestrian_road_maintenance_worker INT4,
    casualty_type             INT4,
    casualty_home_area_type   INT4,
    casualty_imd_decile       INT4,
    lsoa_of_casualty          VARCHAR(20),
    enhanced_casualty_severity INT4,
    casualty_distance_banding INT4,
    
    -- New unique reference computed from accident_index and casualty_reference.
    casualty_unique_ref       VARCHAR(40) GENERATED ALWAYS AS (accident_index || casualty_reference::text) STORED,
    
    -- New computed column to link casualty back to vehicle
    vehicle_unique_ref_for_casualty VARCHAR(60) GENERATED ALWAYS AS (accident_index || vehicle_reference::text) STORED,
    
    CONSTRAINT pk_prod_casualties PRIMARY KEY (casualty_unique_ref),
    CONSTRAINT fk_prod_casualties_collisions FOREIGN KEY (accident_index)
        REFERENCES prod_collisions(accident_index),
    CONSTRAINT fk_prod_casualties_vehicles FOREIGN KEY (vehicle_unique_ref_for_casualty)
        REFERENCES prod_vehicles(vehicle_unique_ref)
);

-- --------------------------
-- Optional: Additional Indexes
-- --------------------------
CREATE INDEX idx_prod_vehicles_accident ON prod_vehicles(accident_index);
CREATE INDEX idx_prod_casualties_accident ON prod_casualties(accident_index);