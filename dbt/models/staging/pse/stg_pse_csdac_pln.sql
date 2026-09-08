with src as (
    select * from {{ source('raw_pse', 'csdac_pln') }}
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
    csdac_pln,
    publication_ts_utc
from dedup
where rn = 1
