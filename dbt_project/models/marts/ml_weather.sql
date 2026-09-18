-- Canonical input to the existing Python feature/target pipeline.
-- Provenance stays in staging; temporal features and labels remain in Python.
select
    temperature, temperature_max, temperature_min, precipitation, humidity,
    wind_speed, solar_radiation, date, site_id,
    latitude, longitude, field_capacity, wilting_point
from {{ ref('stg_weather') }}
