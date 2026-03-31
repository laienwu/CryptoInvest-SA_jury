{% macro log_return(current_col, previous_col) %}
    CASE
        WHEN {{ previous_col }} IS NOT NULL AND {{ previous_col }} > 0
        THEN LN({{ current_col }} / {{ previous_col }})
        ELSE NULL
    END
{% endmacro %}
