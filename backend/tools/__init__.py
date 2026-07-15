"""
Tool registry for AIOps agent tools.

Decorated functions are discovered automatically by the tool loader,
so new tools can be added without changing `agent.py`.
"""

from __future__ import annotations
from typing import Any, Callable

TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def tool(name: str, description: str, parameters: dict):
    def decorator(func: Callable):
        if name in TOOL_REGISTRY:
            raise ValueError(f"Duplicate tool registration: {name}")
        TOOL_REGISTRY[name] = {
            "func": func,
            "description": description,
            "parameters": parameters,
            "module": func.__module__,
        }
        return func

    return decorator
