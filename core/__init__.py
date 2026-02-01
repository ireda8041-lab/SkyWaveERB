# الملف: core/__init__.py
"""
الوحدة الأساسية (Core Module)
تحتوي على المكونات الأساسية للنظام
"""

from .config import Config, config
from .error_handler import ErrorHandler
from .event_bus import EventBus
from .logger import LoggerSetup
from .repository import Repository
from .schemas import *  # noqa: F403

# 🔥 نظام المزامنة الموحد
from .unified_sync import UnifiedSyncManagerV3

__all__ = [
    # Config
    "Config",
    "config",
    # Logger
    "LoggerSetup",
    # Error Handler
    "ErrorHandler",
    # Event Bus
    "EventBus",
    # Repository
    "Repository",
    # 🔥 نظام المزامنة الموحد
    "UnifiedSyncManagerV3",
]
