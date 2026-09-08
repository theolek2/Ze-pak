select
    dtime_utc,
    business_date,
    cor_cost,
    cor_fcst
from {{ ref('stg_pse_cor') }}
