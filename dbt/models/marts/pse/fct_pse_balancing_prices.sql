with cor as (
    select
        dtime_utc,
        business_date,
        'cor' as price_type,
        cor_cost as price
    from {{ ref('stg_pse_cor') }}
),
csdac as (
    select
        dtime_utc,
        business_date,
        'csdac_pln' as price_type,
        csdac_pln as price
    from {{ ref('stg_pse_csdac_pln') }}
)
select * from cor
union all
select * from csdac
