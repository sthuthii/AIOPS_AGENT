try:
    from .tool_loader import load_tools
except Exception:
    from tool_loader import load_tools


def load_tool_specs() -> list[dict]:
    """Load tool metadata from the registered tool functions."""
    tools = load_tools()
    return [
        {
            "name": name,
            "description": meta["description"],
            "parameters": meta["parameters"],
        }
        for name, meta in tools.items()
    ]
