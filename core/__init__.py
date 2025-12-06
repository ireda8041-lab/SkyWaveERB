# الملف: core/__init__.py
"""
الوحدة الأساسية (Core Module)
تحتوي على المكونات الأساسية للنظام
"""

# نظام حل التعارضات الذكي
from .conflict_resolver import (
    ConflictResolution,
    ConflictResolver,
    ConflictResult,
    ConflictSeverity,
)
from .error_handler import ErrorHandler
from .event_bus import EventBus
from .logger import LoggerSetup
from .repository import Repository
from .schemas import *  # noqa: F403
from .smart_sync_manager import SmartSyncManager

__all__ = [
    # Logger
    'LoggerSetup',

    # Error Handler
    'ErrorHandler',

    # Event Bus
    'EventBus',

    # Repository
    'Repository',

    # Conflict Resolution
    'ConflictResolver',
    'ConflictResult',
    'ConflictResolution',
    'ConflictSeverity',
    'SmartSyncManager',
]
