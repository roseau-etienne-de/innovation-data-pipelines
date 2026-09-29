-- Incomplet pour le moment

{% macro add_table_labels(table_ref) -%}
    {%- if config.get("materialized") != "view" -%}
    {% set labels = config.get("labels") %}
    {% set tags = config.get("tags") %}
    {% set job_label = this.name[:63] %}

    {{ print(table_ref.parent) }}

    alter table {{table_ref}}

    set options (labels=[
            ('source', 'dbt'),
            ('environment', '{{target.name}}'),
            ('job', '{{ job_label }}')
            {% if labels is not none and (labels | length) > 0 -%},
                {% for label_name, label_value in labels.items() -%}
            ('{{ label_name }}', '{{ label_value }}')
            {%- if not loop.last %},{% endif %}{%- endfor -%}
            {%- endif -%}
            {% if tags is not none and (tags | length) > 0 -%},
            {% for tag in tags -%} ('pipeline', '{{ tag }}') {% if not loop.last %},{% endif %}{%- endfor -%}
        {%- endif -%}
        ]
    )
    {%- endif -%}
{%- endmacro %}