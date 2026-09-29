SELECT
  CURRENT_DATE() AS datetime
  ,  '{{ var("arg", "no args") }}' AS dbt_cmd_arg
  , "this is a test from openweather 3d job" AS test2
FROM
  {{ source("openweather", "openweather-raw") }}