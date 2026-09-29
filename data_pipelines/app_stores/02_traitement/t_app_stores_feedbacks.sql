{# If not date is given, model will work as an incremental one - Dates format is "YYYY-MM-DD" #}
{% set rattrapage_debut = var('rattrapage_debut', none) %}
{% set rattrapage_fin = var('rattrapage_fin', none) %}

{{
    config(
        materialized="incremental",
        incremental_strategy="insert_overwrite",
        partition_by={
            "field": "date",
            "data_type": "DATE",
            "granularity": "day"
        }
    )
}}

WITH ios_raw AS (
  SELECT * FROM {{ source("app_stores", "e_app_stores_feedbacks_ios_api") }}
  {% if rattrapage_debut and rattrapage_fin %}
    WHERE DATE(createdDate) BETWEEN
      PARSE_DATE('{{ var("date_format") }}', '{{ rattrapage_debut }}')
      AND PARSE_DATE('{{ var("date_format") }}', '{{ rattrapage_fin }}')
  {% elif is_incremental() %}
    WHERE DATE(createdDate) >= CURRENT_DATE() - 1
  {% endif %}
),

android_raw AS (
  SELECT * FROM {{ source("app_stores", "e_android") }}
  {% if rattrapage_debut and rattrapage_fin %}
    WHERE DATE(dateTime) BETWEEN
      PARSE_DATE('{{ var("date_format") }}', '{{ rattrapage_debut }}')
      AND PARSE_DATE('{{ var("date_format") }}', '{{ rattrapage_fin }}')
  {% elif is_incremental() %}
    WHERE DATE(dateTime) >= CURRENT_DATE() - 1
  {% endif %}
),

A AS ( -- Normalisation iOS
  SELECT
    DATE(createdDate) AS date,
    TIMESTAMP(createdDate) AS datetime,
    'iOS' AS OS,
    CONCAT(reviewerNickname, '_', createdDate) AS id,
    rating AS note_num,
    title AS titre,
    body AS verbatims,
    reviewerNickname AS id_name,
    territory AS pays,
    NULL AS langue,
    NULL AS pouce_up,
    NULL AS pouce_down,
    NULL AS device,
    NULL AS manufacturer,
    NULL AS android_os_version
  FROM
    ios_raw
  UNION ALL
    -- Normalisation Android
  SELECT
    DATE(dateTime) AS date,
    TIMESTAMP(dateTime) AS datetime,
    'Android' AS OS,
    reviewId AS id,
    starRating AS note_num,
    NULL AS titre,
    `text` AS verbatims,
    authorName AS id_name,
    NULL AS pays,
    reviewerLanguage AS langue,
    thumbsUpCount AS pouce_up,
    thumbsDownCount AS pouce_down,
    device AS device,
    manufacturer AS manufacturer,
    androidOsVersion AS android_os_version
  FROM
    android_raw )
SELECT
  date,
  datetime,
  OS,
  note_num,
  id,
  titre,
  verbatims,
  id_name,
  pays,
  langue,
  device,
  manufacturer,
  android_os_version
FROM
  A
