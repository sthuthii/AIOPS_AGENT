import importlib
import pkgutil

try:
    from .tools import TOOL_REGISTRY
except Exception:
    from tools import TOOL_REGISTRY


def load_tools() -> dict[str, dict]:
    """Import all tool modules under backend.tools and return the shared registry."""
    package_name = "backend.tools"
    package = importlib.import_module(package_name)
    for finder, name, ispkg in pkgutil.iter_modules(package.__path__):
        if name.startswith("_"):
            continue
        importlib.import_module(f"{package_name}.{name}")
    return TOOL_REGISTRY
