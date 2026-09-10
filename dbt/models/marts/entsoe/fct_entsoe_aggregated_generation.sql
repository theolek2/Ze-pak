{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=[
        'datetime',
        'resolution_code',
        'area_code',
        'production_type',
        'measure_metric'
    ]
) }}

with source_rows as (
    select *
    from {{ ref('stg_entsoe_aggregated_generation') }}
),

unpivoted as (
    select *
    from source_rows
    unpivot (
        actual_mw for measure_metric in (
            actual_generation_output_mw,
            actual_consumption_mw
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
        when measure_metric = 'actual_generation_output_mw' then 'generation_output'
        else 'consumption'
    end as measure_category,
    measure_metric,
    actual_mw
from base
