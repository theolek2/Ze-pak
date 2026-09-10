with source as (
    select * from {{ source('raw', 'imbalance_prices') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by datetime, resolution_code, area_map_code, currency, status
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
    try_cast(positive_imbalance_price as double) as positive_imbalance_price,
    try_cast(positive_scarcity_price as double) as positive_scarcity_price,
    try_cast(positive_incentive_price as double) as positive_incentive_price,
    try_cast(positive_financial_neutrality_price as double) as positive_financial_neutrality_price,
    try_cast(negative_imbalance_price as double) as negative_imbalance_price,
    try_cast(negative_scarcity_price as double) as negative_scarcity_price,
    try_cast(negative_incentive_price as double) as negative_incentive_price,
    try_cast(negative_financial_neutrality_price as double) as negative_financial_neutrality_price,
    currency,
    status,
    update_time
from deduped
where rn = 1
