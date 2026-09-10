with source as (
    select * from {{ source('raw', 'aggregated_generation') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by datetime, resolution_code, area_code, production_type
            order by _dlt_load_id desc
        ) as rn
    from source
)

select
    datetime,
    resolution_code,
    area_code,
    area_name,
    area_type_code,
    area_map_code,
    production_type,
    try_cast(actual_generation_output_mw as double) as actual_generation_output_mw,
    try_cast(actual_consumption_mw as double) as actual_consumption_mw,
    update_time
from deduped
where rn = 1
