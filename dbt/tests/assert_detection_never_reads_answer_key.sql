-- Lineage guard: no model may read the planted answer keys. Only tests may, so detection can't be tuned by peeking.
{% set offenders = [] %}
{% if execute %}
  {% for node in graph.nodes.values() if node.resource_type == 'model' %}
    {% for dep in node.depends_on.nodes if dep.startswith('source.') and '.answer_key.' in dep %}
      {% do offenders.append(node.name ~ ' reads ' ~ dep) %}
    {% endfor %}
  {% endfor %}
{% endif %}
{% if offenders %}
  {% for o in offenders %}select '{{ o }}' as offender{{ " union all" if not loop.last }}
  {% endfor %}
{% else %}
select null as offender where 1 = 0
{% endif %}
