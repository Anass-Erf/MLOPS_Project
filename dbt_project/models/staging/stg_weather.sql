-- Unit conversion and fill-value handling reuse Python normalize_payload before dlt.
-- Strict casts intentionally fail on malformed records; never drop or impute weather.
select
    cast(observed_on as date) as date,
    cast(site_id as varchar) as site_id,
    cast(t2m as double) as temperature,
    cast(t2m_max as double) as temperature_max,
    cast(t2m_min as double) as temperature_min,
    cast(prectotcorr as double) as precipitation,
    cast(rh2m as double) as humidity,
    cast(ws2m as double) as wind_speed,
    cast(allsky_sfc_sw_dwn as double) as solar_radiation,
    cast(latitude as double) as latitude,
    cast(longitude as double) as longitude,
    cast(field_capacity as double) as field_capacity,
    cast(wilting_point as double) as wilting_point,
    cast(source as varchar) as source,
    cast(snapshot_id as varchar) as snapshot_id,
    cast(snapshot_sha256 as varchar) as snapshot_sha256,
    cast(ingested_at as timestamptz) as ingested_at
from {{ source('nasa', 'raw_weather') }}
