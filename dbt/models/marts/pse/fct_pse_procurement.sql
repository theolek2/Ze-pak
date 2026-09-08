with qty as (
    select dtime_utc, business_date, product, quantity_mw
    from {{ ref('stg_pse_mbp_tp') }}
    unpivot (
        quantity_mw for product in (fcr_g, fcr_d, afrr_g, afrr_d, mfrrd_g, mfrrd_d, rr_g)
    )
),
price as (
    select dtime_utc, business_date, product, price_pln_per_mw
    from {{ ref('stg_pse_cmbp_tp') }}
    unpivot (
        price_pln_per_mw for product in (fcr_g, fcr_d, afrr_g, afrr_d, mfrrd_g, mfrrd_d, rr_g)
    )
)
select
    qty.dtime_utc,
    qty.business_date,
    qty.product,
    qty.quantity_mw,
    price.price_pln_per_mw
from qty
left join price
    on qty.dtime_utc = price.dtime_utc
    and qty.business_date = price.business_date
    and qty.product = price.product
