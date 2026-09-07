with source as (
    select * from {{ source('raw', 'energy_prices') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by datetime, resolution_code, area_map_code, contract_type
            order by _dlt_load_id desc
        ) as rn
    from source
)

select
    cast(datetime as timestamp) as datetime,        -- dane UTC; zrzucam bledny offset sesji
    resolution_code,
    area_code,
    area_name,
    area_type_code,
    area_map_code,
    contract_type,
    try_cast(price as double) as price,
    currency,
    cast(update_time as timestamp) as update_time
from deduped
where rn = 1
