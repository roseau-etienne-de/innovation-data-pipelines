{% macro incremental_tmp_table_dropper(bigQueryRelationObject) %}
    {% set tmpTableName %}
        {{ bigQueryRelationObject.database + '.' + bigQueryRelationObject.schema + '.' + bigQueryRelationObject.identifier + '__dbt_tmp'}}
    {% endset %}
    {% set query %}
        drop table if exists {{tmpTableName}};
    {% endset %}

    {{ return(query) }}
{% endmacro %}