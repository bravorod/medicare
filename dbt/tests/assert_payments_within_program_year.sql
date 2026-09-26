{{ config(severity='warn') }}
-- Payment dates should fall inside the program year being analysed.
select payment_record_id, payment_date
from {{ ref('stg_open_payments__general_payments') }}
where payment_date is not null
  and extract(year from payment_date) != {{ var('data_year') }}
