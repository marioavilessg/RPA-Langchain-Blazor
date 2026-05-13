from __future__ import annotations

from typing import Any, Mapping


def render_value(value: Any, params: Mapping[str, Any]) -> Any:
    """Replace {{placeholders}} in string values using the provided params."""
    if not isinstance(value, str):
        return value

    rendered = value
    for key, param_value in params.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(param_value))
    return rendered


def render_mapping(value: Any, params: Mapping[str, Any]) -> Any:
    """Render placeholders recursively in dicts, lists and string leaves."""
    if isinstance(value, dict):
        return {key: render_mapping(item, params) for key, item in value.items()}
    if isinstance(value, list):
        return [render_mapping(item, params) for item in value]
    return render_value(value, params)
