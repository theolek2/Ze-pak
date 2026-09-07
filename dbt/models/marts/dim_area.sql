select distinct
    area_map_code,
    area_code,
    area_name,
    area_type_code
from {{ ref('stg_energy_prices') }}
order by area_map_code
