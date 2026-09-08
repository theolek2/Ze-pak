with src as (
    select * from {{ source('raw_pse', 'cmbp_tp') }}
),
dedup as (
    select *, row_number() over (
        partition by dtime_utc, business_date
        order by _dlt_load_id desc
    ) as rn
    from src
)
select
    dtime_utc,
    cast(business_date as date) as business_date,
    onmb,
    fcr_g, fcr_d, afrr_g, afrr_d, mfrrd_g, mfrrd_d, rr_g,
    publication_ts_utc
from dedup
where rn = 1
