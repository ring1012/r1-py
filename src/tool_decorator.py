"""Lightweight @tool decorator — drop-in replacement for langchain_core.tools.tool.

Features:
  - Parses type hints to build an OpenAI-compatible JSON Schema
  - Parses Google-style Args: docstring sections for per-parameter descriptions
  - Produces a StructuredTool with .name, .description, .openai_schema, and .invoke()
  - Works with instance methods (self) as well as plain functions
  - Zero external dependencies (stdlib only: inspect, typing, re, functools)
"""

import inspect
import re
import functools
from typing import Any, Callable, Optional, get_type_hints


# ---------------------------------------------------------------------------
# Type → JSON Schema helpers
# ---------------------------------------------------------------------------

_PY_TYPE_TO_JSON: dict[Any, str] = {
    str:   "string",
    int:   "integer",
    float: "number",
    bool:  "boolean",
    list:  "array",
    dict:  "object",
}


def _py_type_to_json_type(annotation: Any) -> str:
    """Convert a Python type annotation to a JSON Schema type string."""
    if annotation is inspect.Parameter.empty:
        return "string"

    origin = getattr(annotation, "__origin__", None)

    # Optional[X] → unwrap X
    if origin is type(None):
        return "string"
    if origin is not None:
        # typing.Union / Optional
        args = getattr(annotation, "__args__", ())
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return _py_type_to_json_type(non_none[0])
        return "string"

    return _PY_TYPE_TO_JSON.get(annotation, "string")


# ---------------------------------------------------------------------------
# Docstring parser (Google-style "Args:" section)
# ---------------------------------------------------------------------------

def _parse_arg_descriptions(docstring: str) -> dict[str, str]:
    """Extract per-argument descriptions from a Google-style docstring."""
    descriptions: dict[str, str] = {}
    if not docstring:
        return descriptions

    in_args = False
    current_param: str | None = None
    current_lines: list[str] = []

    for raw_line in docstring.splitlines():
        line = raw_line.rstrip()
        stripped = line.lstrip()

        if re.match(r"^Args\s*:", stripped):
            in_args = True
            continue

        # Any other top-level section ends the Args block
        if in_args and re.match(r"^\w[\w\s]*:", stripped) and not line.startswith(" "):
            in_args = False

        if not in_args:
            continue

        # Detect "    param_name: description" lines (exactly 4+ spaces indent)
        param_match = re.match(r"^\s{4}(\w+)\s*:\s*(.*)", line)
        if param_match:
            # Save previous param
            if current_param is not None:
                descriptions[current_param] = " ".join(current_lines).strip()
            current_param = param_match.group(1)
            current_lines = [param_match.group(2)]
        elif current_param and line.startswith("        "):
            # Continuation line for the current param
            current_lines.append(stripped)

    if current_param is not None:
        descriptions[current_param] = " ".join(current_lines).strip()

    return descriptions


# ---------------------------------------------------------------------------
# Schema builder
# ---------------------------------------------------------------------------

def _build_openai_schema(func: Callable) -> dict:
    """Build an OpenAI function schema from a callable's signature and docstring."""
    sig = inspect.signature(func)
    try:
        hints = get_type_hints(func)
    except Exception:
        hints = {}

    docstring = inspect.getdoc(func) or ""
    # First line is the summary description; strip "Args:" and below
    description_lines = []
    for line in docstring.splitlines():
        if re.match(r"^Args\s*:", line.strip()):
            break
        if re.match(r"^samples\s*:", line.strip(), re.I):
            break
        description_lines.append(line)
    description = "\n".join(description_lines).strip()

    arg_descriptions = _parse_arg_descriptions(docstring)

    properties: dict[str, dict] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        annotation = hints.get(param_name, inspect.Parameter.empty)
        json_type = _py_type_to_json_type(annotation)

        prop: dict[str, Any] = {"type": json_type}
        if param_name in arg_descriptions:
            prop["description"] = arg_descriptions[param_name]

        properties[param_name] = prop

        # Parameter is required if it has no default value and is not Optional
        origin = getattr(annotation, "__origin__", None)
        is_optional = origin is not None and type(None) in getattr(annotation, "__args__", ())
        if param.default is inspect.Parameter.empty and not is_optional:
            required.append(param_name)

    schema = {
        "name": func.__name__,
        "description": description,
        "parameters": {
            "type": "object",
            "properties": properties,
        },
    }
    if required:
        schema["parameters"]["required"] = required

    return schema


# ---------------------------------------------------------------------------
# StructuredTool wrapper
# ---------------------------------------------------------------------------

class StructuredTool:
    """Callable tool wrapper produced by the @tool decorator."""

    def __init__(self, func: Callable, schema: dict):
        self._func = func
        self.openai_schema = schema
        self.name: str = schema["name"]
        self.description: str = schema.get("description", "")
        functools.update_wrapper(self, func)

    # ------------------------------------------------------------------
    # Invocation
    # ------------------------------------------------------------------

    def invoke(self, args: dict | None = None) -> Any:
        """Invoke the underlying function with keyword arguments."""
        return self._func(**(args or {}))

    def __call__(self, *args, **kwargs) -> Any:
        return self._func(*args, **kwargs)

    def __repr__(self) -> str:
        return f"StructuredTool(name={self.name!r})"


# ---------------------------------------------------------------------------
# @tool decorator
# ---------------------------------------------------------------------------

def tool(func: Callable | None = None, *, name: str | None = None) -> Any:
    """Decorator that converts a function (or bound method) into a StructuredTool.

    Usage:
        @tool
        def my_function(x: str) -> dict:
            \"\"\"Does something useful.\"\"\"
            ...

    The decorator can be applied to **instance methods** (with a ``self``
    parameter).  In that case, invoking the result from an instance will
    still work correctly because we bind the method at decoration time when
    the instance is available, or lazily via __get__.
    """
    if func is None:
        # Called as @tool() with parentheses but no arguments - handle gracefully
        def decorator(f):
            return _make_tool(f, name=name)
        return decorator

    return _make_tool(func, name=name)


def _make_tool(func: Callable, *, name: str | None = None) -> "ToolDescriptor":
    """Wrap func in a ToolDescriptor to support both functions and methods."""
    return ToolDescriptor(func, override_name=name)


# ---------------------------------------------------------------------------
# Descriptor to handle both free functions and instance methods
# ---------------------------------------------------------------------------

class ToolDescriptor:
    """Descriptor wrapper so @tool works on both module-level functions and methods."""

    def __init__(self, func: Callable, override_name: str | None = None):
        self._func = func
        self._override_name = override_name
        functools.update_wrapper(self, func)

    # When accessed on an instance (e.g. self.play_music) bind the method
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self          # accessed on the class itself
        bound = functools.partial(self._func, obj)
        bound.__name__ = self._func.__name__   # type: ignore[attr-defined]
        bound.__doc__ = self._func.__doc__
        # Copy annotations so the schema builder sees them
        bound.__annotations__ = getattr(self._func, "__annotations__", {})  # type: ignore[attr-defined]
        schema = _build_openai_schema(bound)
        if self._override_name:
            schema["name"] = self._override_name
        return StructuredTool(bound, schema)

    # When called directly (not via instance), build a plain StructuredTool
    def __call__(self, *args, **kwargs):
        return self._func(*args, **kwargs)

    def invoke(self, args: dict | None = None) -> Any:
        return self._func(**(args or {}))

    @property
    def name(self) -> str:
        if self._override_name:
            return self._override_name
        return self._func.__name__

    @property
    def openai_schema(self) -> dict:
        return _build_openai_schema(self._func)
