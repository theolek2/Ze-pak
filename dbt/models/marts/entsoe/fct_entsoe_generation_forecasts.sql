{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=[
        'datetime',
        'resolution_code',
        'area_code',
        'production_type',
        'forecast_metric'
    ]
) }}

with source_rows as (
    select *
    from {{ ref('stg_entsoe_generation_forecasts') }}
),

unpivoted as (
    select *
    from source_rows
    unpivot (
        forecast_mw for forecast_metric in (
            day_ahead_generation_forecast_mw,
            intraday_generation_forecast_mw,
            current_generation_forecast_mw
        )
    )
),

base as (
    select * from unpivoted
)

select
    datetime,
    area_code,
    area_name,
    area_type_code,
    area_map_code,
    resolution_code,
    production_type,
    update_time,
    case
        when forecast_metric = 'day_ahead_generation_forecast_mw' then 'day_ahead'
        when forecast_metric = 'intraday_generation_forecast_mw' then 'intraday'
        else 'current'
    end as forecast_category,
    forecast_metric,
    forecast_mw
from base
