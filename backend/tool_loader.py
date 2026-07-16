import importlib
import pkgutil

if __package__:
    from .tools import TOOL_REGISTRY

    TOOLS_PACKAGE_NAME = "backend.tools"
else:
    from tools import TOOL_REGISTRY

    TOOLS_PACKAGE_NAME = "tools"


def load_tools() -> dict[str, dict]:
    """Import all tool modules under backend.tools and return the shared registry."""
    package_name = TOOLS_PACKAGE_NAME
    package = importlib.import_module(package_name)
    for finder, name, ispkg in pkgutil.iter_modules(package.__path__):
        if name.startswith("_"):
            continue
        importlib.import_module(f"{package_name}.{name}")
    return TOOL_REGISTRY
