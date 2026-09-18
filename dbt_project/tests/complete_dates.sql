-- Includes missing entire sites, endpoints, interior gaps and extra observations.
with expected as (
    {% for site in var('known_sites') %}
    select '{{ site }}' as site_id, cast(day as date) as date
    from generate_series(
        date '{{ var("weather_start") }}', date '{{ var("weather_end") }}', interval 1 day
    ) as days(day)
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
), actual as (select site_id, date from {{ ref('ml_weather') }})
select coalesce(e.site_id, a.site_id) as site_id, coalesce(e.date, a.date) as date
from expected e full outer join actual a using (site_id, date)
where e.site_id is null or a.site_id is null
