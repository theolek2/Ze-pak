with src as (
    select * from {{ source('raw_pse', 'zmb') }}
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
    zmb_fcrg, zmb_fcrd, zmb_frrg, zmb_frrd,
    zmb_afrrg, zmb_afrrd, zmb_rrg, zmb_rrd,
    publication_ts_utc
from dedup
where rn = 1
