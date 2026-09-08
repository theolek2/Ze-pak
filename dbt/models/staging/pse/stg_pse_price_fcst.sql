with src as (
    select * from {{ source('raw_pse', 'price_fcst') }}
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
    cen_fcst, cor_fcst, ckoeb_fcst, imb_energy, ceb_sr_fcst, contracting,
    publication_ts_utc
from dedup
where rn = 1
