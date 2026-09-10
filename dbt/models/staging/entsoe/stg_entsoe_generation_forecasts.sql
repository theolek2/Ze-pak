with source as (
    select * from {{ source('raw', 'generation_forecasts') }}
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
    try_cast(day_ahead_generation_forecast_mw as double) as day_ahead_generation_forecast_mw,
    try_cast(intraday_generation_forecast_mw as double) as intraday_generation_forecast_mw,
    try_cast(current_generation_forecast_mw as double) as current_generation_forecast_mw,
    update_time
from deduped
where rn = 1
