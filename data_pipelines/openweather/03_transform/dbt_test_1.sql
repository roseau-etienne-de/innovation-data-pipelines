SELECT
  CURRENT_DATE() AS datetime
  , ville
  , pays
  , meteo
  , temperature
  , "this is a test 1 from openweather 3d job" AS test1
FROM
  {{ source("openweather", "openweather-raw") }} 