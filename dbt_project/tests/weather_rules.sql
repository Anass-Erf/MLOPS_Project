-- Bounds are the existing validate_weather contract, not new agronomic thresholds.
select * from {{ ref('ml_weather') }}
where temperature not between -60 and 60
   or temperature_max not between -60 and 65
   or temperature_min not between -70 and 60
   or precipitation not between 0 and 1000
   or humidity not between 0 and 100
   or wind_speed not between 0 and 75
   or solar_radiation not between 0 and 50
   or temperature_min > temperature or temperature > temperature_max
   or not (0 < wilting_point and wilting_point < field_capacity and field_capacity < 1)
