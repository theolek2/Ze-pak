select
    datetime,
    area_map_code,
    resolution_code,
    contract_type,
    price,
    currency
from {{ ref('stg_energy_prices') }}
