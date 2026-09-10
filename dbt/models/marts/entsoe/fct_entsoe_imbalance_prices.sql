{{ config(
    materialized='incremental',
    incremental_strategy='merge',
    unique_key=[
        'datetime',
        'resolution_code',
        'area_map_code',
        'currency',
        'status',
        'price_metric'
    ]
) }}

with source_rows as (
    select *
    from {{ ref('stg_entsoe_imbalance_prices') }}
),

unpivoted as (
    select *
    from source_rows
    unpivot (
        price for price_metric in (
            positive_imbalance_price,
            positive_scarcity_price,
            positive_incentive_price,
            positive_financial_neutrality_price,
            negative_imbalance_price,
            negative_scarcity_price,
            negative_incentive_price,
            negative_financial_neutrality_price
        )
    )
),

base as (
    select * from unpivoted
)

select
    datetime,
    area_map_code,
    resolution_code,
    currency,
    status,
    update_time,
    case
        when price_metric like 'positive_%' then 'positive'
        when price_metric like 'negative_%' then 'negative'
    end as direction,
    case
        when price_metric like '%_imbalance_price' then 'imbalance'
        when price_metric like '%_scarcity_price' then 'scarcity'
        when price_metric like '%_incentive_price' then 'incentive'
        when price_metric like '%_financial_neutrality_price' then 'financial_neutrality'
    end as price_category,
    price_metric,
    price
from base
