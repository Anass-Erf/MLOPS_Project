select site_id, date, count(*) as observations
from {{ ref('ml_weather') }}
group by site_id, date
having count(*) <> 1
