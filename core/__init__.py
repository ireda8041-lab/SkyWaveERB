from __future__ import annotations

"""الواجهة العامة لوحدة Core مع تحميل كسول لتقليل كلفة startup."""

from importlib import import_module

__all__ = [
    "Config",
    "config",
    "LoggerSetup",
    "ErrorHandler",
    "EventBus",
    "Repository",
    "UnifiedSyncManagerV3",
    "schemas",
]

_LAZY_EXPORTS = {
    "Config": ("core.config", "Config"),
    "config": ("core.config", "config"),
    "LoggerSetup": ("core.logger", "LoggerSetup"),
    "ErrorHandler": ("core.error_handler", "ErrorHandler"),
    "EventBus": ("core.event_bus", "EventBus"),
    "Repository": ("core.repository", "Repository"),
    "UnifiedSyncManagerV3": ("core.unified_sync", "UnifiedSyncManagerV3"),
    "schemas": ("core.schemas", None),
}


def _load_export(name: str):
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    value = module if attr_name is None else getattr(module, attr_name)
    globals()[name] = value
    return value


def __getattr__(name: str):
    if name in _LAZY_EXPORTS:
        return _load_export(name)

    schemas_module = import_module("core.schemas")
    if hasattr(schemas_module, name):
        value = getattr(schemas_module, name)
        globals()[name] = value
        return value

    raise AttributeError(f"module 'core' has no attribute {name!r}")


def __dir__():
    schemas_module = import_module("core.schemas")
    return sorted(set(globals()) | set(__all__) | set(dir(schemas_module)))
