from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import Any


def resolve_python_entrypoint(entrypoint: str) -> Callable[..., Any]:
    if ":" not in entrypoint:
        raise ValueError("Python entrypoint must use 'module:function' format.")
    module_name, attribute_name = entrypoint.split(":", 1)
    if not module_name or not attribute_name:
        raise ValueError("Python entrypoint must use 'module:function' format.")

    module = import_module(module_name)
    target: Any = module
    for part in attribute_name.split("."):
        target = getattr(target, part)
    if not callable(target):
        raise TypeError(f"Python entrypoint '{entrypoint}' is not callable.")
    return target


def execute_python_entrypoint(entrypoint: str, *args: Any, **kwargs: Any) -> Any:
    return resolve_python_entrypoint(entrypoint)(*args, **kwargs)
