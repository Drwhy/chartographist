import os
import importlib

EVENT_INFRASTRUCTURE_MODULES = {
    "__init__",
    "base_event",
    "event_registry",
    "event_manager",
}


def discover_event_modules():
    """Return concrete event modules in a stable order."""
    package_dir = os.path.dirname(__file__)
    modules = [
        filename[:-3]
        for filename in os.listdir(package_dir)
        if filename.endswith(".py") and filename[:-3] not in EVENT_INFRASTRUCTURE_MODULES
    ]
    return sorted(modules)


for event_module in discover_event_modules():
    importlib.import_module(f"events.{event_module}")