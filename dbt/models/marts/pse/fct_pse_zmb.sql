with stg as (
    select dtime_utc, business_date, product, demand_mw
    from {{ ref('stg_pse_zmb') }}
    unpivot (
        demand_mw for product in (
            zmb_fcrg, zmb_fcrd, zmb_frrg, zmb_frrd,
            zmb_afrrg, zmb_afrrd, zmb_rrg, zmb_rrd
        )
    )
)
select
    dtime_utc,
    business_date,
    product,
    demand_mw
from stg
