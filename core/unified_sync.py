# الملف: core/unified_sync.py
"""
🔄 نظام المزامنة الموحد - MongoDB First
MongoDB هو المصدر الرئيسي، SQLite نسخة محلية للـ offline فقط

المبدأ:
- عند الاتصال: MongoDB = الحقيقة المطلقة
- عند عدم الاتصال: SQLite يحفظ التغييرات مؤقتاً
- عند استعادة الاتصال: رفع التغييرات المحلية ثم مسح وإعادة تحميل من MongoDB
"""

import json
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.device_identity import get_stable_device_id
from core.logger import get_logger
from core.sqlite_identifiers import quote_identifier, quote_identifier_list

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


logger = get_logger(__name__)

# ==================== ثوابت التوقيت (بالمللي ثانية) ====================
FULL_SYNC_INTERVAL_MS = 15 * 60 * 1000
QUICK_SYNC_INTERVAL_MS = 3 * 60 * 1000
CONNECTION_CHECK_INTERVAL_MS = 90 * 1000
CLOUD_PULL_INTERVAL_MS = 45 * 1000
DEFAULT_DELTA_SYNC_INTERVAL_SECONDS = 2
DEFAULT_REALTIME_CHANGE_STREAM_MAX_AWAIT_MS = 250
DEFAULT_LAZY_LOGO_ENABLED = True
DEFAULT_LOGO_FETCH_BATCH_LIMIT = 10
DEFAULT_DELTA_PUSH_BATCH_LIMIT = 40
DEFAULT_SYNC_PING_COOLDOWN_SECONDS = 5.0
DEFAULT_INSTANT_SYNC_DEDUPE_MS = 900
DEFAULT_REALTIME_PULL_DEDUPE_MS = 900
DEFAULT_MIN_FULL_SYNC_WHEN_DELTA_ACTIVE_SECONDS = 1800


class UnifiedSyncManagerV3(QObject):
    """
    مدير المزامنة الموحد - MongoDB First Architecture
    مع نظام مزامنة تلقائية احترافي
    """

    # الإشارات
    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(str, int, int)  # table, current, total
    sync_completed = pyqtSignal(dict)
    sync_error = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)  # online/offline
    data_synced = pyqtSignal()  # ⚡ NEW: Signal emitted after successful pull for UI refresh

    # الجداول المدعومة
    TABLES = [
        "accounts",
        "clients",
        "services",
        "quotations",
        "projects",
        "invoices",
        "payments",
        "expenses",
        "journal_entries",
        "currencies",
        "notifications",
        "tasks",
    ]

    # الحقول الفريدة لكل جدول
    UNIQUE_FIELDS = {
        "clients": "name",
        "projects": "name",
        "services": "name",
        "quotations": "quotation_number",
        "accounts": "code",
        "invoices": "invoice_number",
        "payments": "id",
        "expenses": "id",
        "journal_entries": "id",
        "currencies": "code",
        "users": "username",
        "notifications": "id",
        "tasks": "id",
    }

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self._lock = threading.RLock()
        self._delta_cycle_lock = threading.Lock()
        self._full_sync_dispatch_lock = threading.Lock()
        self._is_syncing = False
        self._full_sync_thread_in_flight = False
        self._max_retries = 3
        self._last_online_status = bool(getattr(repository, "online", False))
        self._online_status_lock = threading.Lock()
        self._last_online_probe_mono = time.monotonic()
        self._online_status_cache_ttl_seconds = 1.2
        self._connection_probe_lock = threading.Lock()
        self._connection_probe_in_flight = False
        self._shutdown = False  # ⚡ علامة الإغلاق
        self._last_full_sync_at = None
        self._sync_metrics_lock = threading.RLock()
        self._sync_metrics = {
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "last_sync_time": None,
            "total_records_synced": 0,
        }

        # ⚡ إعدادات المزامنة التلقائية - مفعّلة للمزامنة بين الأجهزة
        self._auto_sync_enabled = True
        self._auto_sync_interval = FULL_SYNC_INTERVAL_MS
        self._quick_sync_interval = QUICK_SYNC_INTERVAL_MS
        self._connection_check_interval = CONNECTION_CHECK_INTERVAL_MS
        self._delta_sync_interval_seconds = DEFAULT_DELTA_SYNC_INTERVAL_SECONDS
        self._realtime_enabled = True
        self._realtime_auto_detect = True
        self._realtime_change_stream_max_await_ms = DEFAULT_REALTIME_CHANGE_STREAM_MAX_AWAIT_MS
        self._lazy_logo_enabled = DEFAULT_LAZY_LOGO_ENABLED
        self._logo_fetch_batch_limit = DEFAULT_LOGO_FETCH_BATCH_LIMIT
        self._realtime_pull_dedupe_ms = DEFAULT_REALTIME_PULL_DEDUPE_MS
        self._last_realtime_pull_ms: dict[str, int] = {}
        self._queued_realtime_tables: set[str] = set()
        self._instant_sync_schedule_lock = threading.Lock()
        self._instant_sync_pending_tables: set[str] = set()
        self._instant_sync_worker_running = False
        self._instant_sync_dedupe_ms = DEFAULT_INSTANT_SYNC_DEDUPE_MS
        self._last_instant_sync_request_ms: dict[str, int] = {}
        self._device_id = get_stable_device_id()
        self._last_sync_ping_at: dict[str, float] = {}
        self._sync_ping_cooldown_seconds = DEFAULT_SYNC_PING_COOLDOWN_SECONDS
        self._delta_push_batch_limit = DEFAULT_DELTA_PUSH_BATCH_LIMIT
        self._min_full_sync_when_delta_active_seconds = (
            DEFAULT_MIN_FULL_SYNC_WHEN_DELTA_ACTIVE_SECONDS
        )
        self._last_delta_cycle_mono = 0.0
        self._last_delta_change_mono = 0.0

        # ⚡ المؤقتات
        self._auto_sync_timer = None
        self._quick_sync_timer = None
        self._connection_timer = None
        self._cloud_pull_timer = None
        self._delta_pull_timer = None  # ⚡ NEW: مؤقت السحب التفاضلي
        self._delta_thread = None
        self._delta_thread_stop = threading.Event()

        self._load_sync_config()

        # ⚡ Watermarks للـ Delta Sync
        self._watermarks: dict[str, str] = {}
        self._load_watermarks()
        self._table_exists_cache: dict[str, bool] = {}
        self._table_columns_cache: dict[str, set[str]] = {}

        logger.info("✅ تم تهيئة UnifiedSyncManager - مزامنة محسّنة للأداء")

    def _emit_sync_pings(self, tables: set[str]) -> None:
        if not tables:
            return
        if not self.is_online or self.repo is None or self.repo.mongo_db is None:
            return
        collection = self.repo.mongo_db["notifications"]
        now_iso = self._to_iso_timestamp(self._get_mongo_server_now())
        now_ts = time.time()
        for table in tables:
            # Avoid notification table echo storms.
            if table == "notifications":
                continue
            last_ping = self._last_sync_ping_at.get(table, 0.0)
            if (now_ts - last_ping) < self._sync_ping_cooldown_seconds:
                continue
            self._last_sync_ping_at[table] = now_ts
            payload = {
                "message": f"sync ping: {table}",
                "type": "info",
                "title": "sync",
                "device_id": self._device_id,
                "created_at": now_iso,
                "entity_type": table,
                "action": "sync_ping",
                "silent": True,
            }
            try:
                collection.insert_one(payload)
            except Exception as e:
                logger.debug("تعذر إرسال sync ping لـ %s: %s", table, e)

    def emit_sync_ping_for_table(self, table: str | None) -> bool:
        """
        Public helper used by app signals to notify other devices immediately
        even when no local dirty rows are pending for push.
        """
        table_key = self._normalize_table_key(table)
        if table_key == "__all__":
            return False
        if self._shutdown or not self.is_online:
            return False
        if self.repo is None or self.repo.mongo_db is None:
            return False
        try:
            self._emit_sync_pings({table_key})
            return True
        except Exception as e:
            logger.debug("تعذر بث sync ping فوري للجدول %s: %s", table_key, e)
            return False

    def _update_sync_metrics(self, success: bool, records_synced: int = 0):
        """Update lightweight sync counters used by settings UI."""
        try:
            with self._sync_metrics_lock:
                self._sync_metrics["total_syncs"] += 1
                if success:
                    self._sync_metrics["successful_syncs"] += 1
                    self._sync_metrics["total_records_synced"] += max(0, int(records_synced))
                else:
                    self._sync_metrics["failed_syncs"] += 1
                self._sync_metrics["last_sync_time"] = datetime.now().isoformat()
        except Exception:
            # Metrics are non-critical.
            pass

    @staticmethod
    def _safe_int(value: Any, default: int, minimum: int = 1, maximum: int | None = None) -> int:
        """Convert a value to int with sane bounds."""
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = int(default)
        if parsed < minimum:
            parsed = minimum
        if maximum is not None and parsed > maximum:
            parsed = maximum
        return parsed

    def _load_sync_config(self):
        """Load sync intervals from sync_config.json if available."""
        try:
            config_path = Path("sync_config.json")
            if not config_path.exists():
                return

            with open(config_path, encoding="utf-8") as f:
                config = json.load(f)

            self._auto_sync_enabled = bool(config.get("enabled", self._auto_sync_enabled))

            default_auto_seconds = max(1, self._auto_sync_interval // 1000)
            default_quick_seconds = max(1, self._quick_sync_interval // 1000)
            default_connection_seconds = max(1, self._connection_check_interval // 1000)

            auto_seconds = self._safe_int(
                config.get("auto_sync_interval", default_auto_seconds),
                default_auto_seconds,
                minimum=30,
                maximum=3600,
            )
            quick_seconds = self._safe_int(
                config.get("quick_sync_interval", default_quick_seconds),
                default_quick_seconds,
                minimum=1,
                maximum=300,
            )
            connection_seconds = self._safe_int(
                config.get("connection_check_interval", default_connection_seconds),
                default_connection_seconds,
                minimum=1,
                maximum=300,
            )
            delta_seconds = self._safe_int(
                config.get("delta_sync_interval", DEFAULT_DELTA_SYNC_INTERVAL_SECONDS),
                DEFAULT_DELTA_SYNC_INTERVAL_SECONDS,
                minimum=1,
                maximum=300,
            )
            realtime_max_await_ms = self._safe_int(
                config.get(
                    "realtime_change_stream_max_await_ms",
                    DEFAULT_REALTIME_CHANGE_STREAM_MAX_AWAIT_MS,
                ),
                DEFAULT_REALTIME_CHANGE_STREAM_MAX_AWAIT_MS,
                minimum=50,
                maximum=5000,
            )
            logo_fetch_batch_limit = self._safe_int(
                config.get("logo_fetch_batch_limit", DEFAULT_LOGO_FETCH_BATCH_LIMIT),
                DEFAULT_LOGO_FETCH_BATCH_LIMIT,
                minimum=1,
                maximum=100,
            )
            self._delta_push_batch_limit = self._safe_int(
                config.get("delta_push_batch_limit", DEFAULT_DELTA_PUSH_BATCH_LIMIT),
                DEFAULT_DELTA_PUSH_BATCH_LIMIT,
                minimum=10,
                maximum=500,
            )
            self._instant_sync_dedupe_ms = self._safe_int(
                config.get("instant_sync_dedupe_ms", DEFAULT_INSTANT_SYNC_DEDUPE_MS),
                DEFAULT_INSTANT_SYNC_DEDUPE_MS,
                minimum=100,
                maximum=5000,
            )
            self._realtime_pull_dedupe_ms = self._safe_int(
                config.get("realtime_pull_dedupe_ms", DEFAULT_REALTIME_PULL_DEDUPE_MS),
                DEFAULT_REALTIME_PULL_DEDUPE_MS,
                minimum=100,
                maximum=5000,
            )
            try:
                ping_cooldown = float(
                    config.get("sync_ping_cooldown_s", DEFAULT_SYNC_PING_COOLDOWN_SECONDS)
                )
            except (TypeError, ValueError):
                ping_cooldown = DEFAULT_SYNC_PING_COOLDOWN_SECONDS
            self._sync_ping_cooldown_seconds = max(0.5, min(30.0, ping_cooldown))
            self._min_full_sync_when_delta_active_seconds = self._safe_int(
                config.get(
                    "min_full_sync_when_delta_active_seconds",
                    DEFAULT_MIN_FULL_SYNC_WHEN_DELTA_ACTIVE_SECONDS,
                ),
                DEFAULT_MIN_FULL_SYNC_WHEN_DELTA_ACTIVE_SECONDS,
                minimum=300,
                maximum=7200,
            )

            self._auto_sync_interval = auto_seconds * 1000
            self._quick_sync_interval = quick_seconds * 1000
            self._connection_check_interval = connection_seconds * 1000
            self._delta_sync_interval_seconds = delta_seconds
            self._realtime_enabled = bool(config.get("realtime_enabled", self._realtime_enabled))
            self._realtime_auto_detect = bool(
                config.get("realtime_auto_detect", self._realtime_auto_detect)
            )
            self._realtime_change_stream_max_await_ms = realtime_max_await_ms
            self._lazy_logo_enabled = bool(
                config.get("lazy_logo_enabled", DEFAULT_LAZY_LOGO_ENABLED)
            )
            self._logo_fetch_batch_limit = logo_fetch_batch_limit

            logger.info(
                "⚙️ تم تحميل إعدادات المزامنة: full=%ss quick=%ss connection=%ss delta=%ss enabled=%s realtime=%s lazy_logo=%s",
                auto_seconds,
                quick_seconds,
                connection_seconds,
                delta_seconds,
                self._auto_sync_enabled,
                self._realtime_enabled,
                self._lazy_logo_enabled,
            )
        except Exception as e:
            logger.debug("فشل تحميل sync_config.json: %s", e)

    def _check_mongodb_connection(self) -> bool:
        try:
            if not self.is_online:
                return False
            if self.repo.mongo_db is None or self.repo.mongo_client is None:
                logger.warning("MongoDB client أو database غير متوفر")
                return False
            self.repo.mongo_client.admin.command("ping", maxTimeMS=5000)
            server_info = self.repo.mongo_client.server_info()
            if not server_info:
                logger.warning("فشل الحصول على معلومات الخادم")
                return False
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "cannot use mongoclient after close" in error_msg:
                logger.debug("MongoDB client مغلق")
            elif "serverselectiontimeout" in error_msg:
                logger.debug("انتهت مهلة الاتصال بـ MongoDB")
            elif "network" in error_msg or "connection" in error_msg:
                logger.debug("مشكلة في الشبكة مع MongoDB")
            else:
                logger.warning("خطأ في فحص MongoDB: %s", e)
            return False

    def _safe_mongodb_operation(self, operation_func, *args, **kwargs):
        try:
            if not self._check_mongodb_connection():
                return None
            return operation_func(*args, **kwargs)
        except Exception as e:
            logger.error("فشل عملية MongoDB: %s", e, exc_info=True)
            return None

    @staticmethod
    def _is_closed_sqlite_error(exc: Exception) -> bool:
        return "closed database" in str(exc).lower()

    @staticmethod
    def _to_iso_timestamp(value: Any) -> str:
        """Normalize timestamp values from Mongo/SQLite to ISO string."""
        if value is None:
            return ""
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ""
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                return parsed.isoformat()
            except ValueError:
                return text
        if hasattr(value, "isoformat"):
            try:
                iso_text = value.isoformat()
                parsed = datetime.fromisoformat(str(iso_text).replace("Z", "+00:00"))
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
                return parsed.isoformat()
            except Exception:
                return str(value)
        return str(value)

    @staticmethod
    def _parse_iso_datetime(value: Any) -> datetime | None:
        """Parse ISO timestamp string safely."""
        if not isinstance(value, str) or not value.strip():
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _normalize_datetime(value: datetime | None) -> datetime | None:
        """Normalize datetimes for safe comparisons (convert aware -> naive UTC)."""
        if value is None:
            return None
        if value.tzinfo is not None:
            try:
                return value.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                return value.replace(tzinfo=None)
        return value

    def _get_mongo_server_now(self) -> datetime:
        """
        Return server-side current time when possible.
        Using server time avoids cross-device clock drift in last_modified watermarks.
        """
        try:
            if self.repo is None or self.repo.mongo_client is None:
                return datetime.now()
            hello = self.repo.mongo_client.admin.command("hello")
            server_now = hello.get("localTime")
            if hasattr(server_now, "isoformat"):
                normalized = self._normalize_datetime(server_now)
                if normalized is not None:
                    return normalized
            return datetime.now()
        except Exception:
            return datetime.now()

    def _build_last_modified_query(
        self, watermark: str, upper_bound_dt: datetime | None = None
    ) -> dict[str, Any]:
        """
        Build query that handles mixed datetime/string storage in MongoDB safely.

        Important: do not compare dates to string directly in a single condition,
        because BSON cross-type ordering can make `date > "string"` always true and
        cause full-table pulls on every cycle.
        """
        watermark_str = str(watermark or "")
        watermark_dt = self._parse_iso_datetime(watermark_str)
        upper_bound_str = (
            upper_bound_dt.isoformat() if hasattr(upper_bound_dt, "isoformat") else None
        )
        branches: list[dict[str, Any]] = []

        if watermark_dt is not None:
            date_cond: dict[str, Any] = {"$gt": watermark_dt}
            if upper_bound_dt is not None:
                date_cond["$lte"] = upper_bound_dt
            branches.append(
                {
                    "$and": [
                        {"last_modified": {"$type": "date"}},
                        {"last_modified": date_cond},
                    ]
                }
            )

        if watermark_str:
            string_cond: dict[str, Any] = {"$gt": watermark_str}
            if upper_bound_str:
                string_cond["$lte"] = upper_bound_str
            branches.append(
                {
                    "$and": [
                        {"last_modified": {"$type": "string"}},
                        {"last_modified": string_cond},
                    ]
                }
            )

        if not branches:
            return {"last_modified": {"$exists": True}}
        return branches[0] if len(branches) == 1 else {"$or": branches}

    @staticmethod
    def _to_safe_float(value: Any, default: float = 0.0) -> float:
        if value is None or value == "":
            return float(default)
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _to_safe_int(value: Any, default: int = 0) -> int:
        if value is None or value == "":
            return int(default)
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return int(default)

    @staticmethod
    def _to_safe_bool_int(value: Any) -> int:
        if isinstance(value, bool):
            return 1 if value else 0
        if isinstance(value, int | float):
            return 1 if int(value) != 0 else 0
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return 1
            if normalized in {"0", "false", "no", "off", ""}:
                return 0
        return 0

    @staticmethod
    def _merge_query_with_notification_filter(base_query: dict[str, Any]) -> dict[str, Any]:
        """
        Ignore operational sync ping notifications in generic table synchronization.
        Notification toasts are handled by dedicated notification workers.
        """
        sync_ping_filter = {
            "$and": [
                {"$or": [{"action": {"$exists": False}}, {"action": {"$ne": "sync_ping"}}]},
                {"$or": [{"silent": {"$exists": False}}, {"silent": {"$ne": True}}]},
                {
                    "$or": [
                        {"transport_only": {"$exists": False}},
                        {"transport_only": {"$ne": True}},
                    ]
                },
                {
                    "$or": [
                        {"device_id": {"$exists": False}},
                        {"last_modified": {"$exists": True}},
                        {"priority": {"$exists": True}},
                    ]
                },
            ]
        }
        if not base_query:
            return sync_ping_filter
        return {"$and": [base_query, sync_ping_filter]}

    def _is_newer_timestamp(self, candidate: Any, reference: Any) -> bool:
        """
        True when candidate timestamp is strictly newer than reference timestamp.
        Handles mixed datetime/string formats safely.
        """
        candidate_iso = self._to_iso_timestamp(candidate)
        reference_iso = self._to_iso_timestamp(reference)
        if not candidate_iso:
            return False
        if not reference_iso:
            return True

        candidate_dt = self._normalize_datetime(self._parse_iso_datetime(candidate_iso))
        reference_dt = self._normalize_datetime(self._parse_iso_datetime(reference_iso))
        if candidate_dt is not None and reference_dt is not None:
            return candidate_dt > reference_dt
        return candidate_iso > reference_iso

    @staticmethod
    def _linked_project_field(table_name: str) -> str | None:
        return {
            "payments": "project_id",
            "expenses": "project_id",
            "invoices": "project_id",
            "quotations": "converted_to_project_id",
            "tasks": "related_project_id",
        }.get(table_name)

    @staticmethod
    def _linked_project_client_field(table_name: str) -> str | None:
        return {
            "payments": "client_id",
            "invoices": "client_id",
            "quotations": "client_id",
            "tasks": "related_client_id",
        }.get(table_name)

    def _normalize_project_links_for_push(
        self,
        cursor,
        table_name: str,
        record: dict[str, Any],
        table_columns: set[str],
        server_now_iso: str,
    ) -> dict[str, Any]:
        project_field = self._linked_project_field(table_name)
        if not project_field or project_field not in table_columns:
            return record

        resolve_project = getattr(self.repo, "_resolve_project_target_row", None)
        stable_project_ref = getattr(self.repo, "_stable_project_reference", None)
        normalize_client_ref = getattr(self.repo, "_normalize_client_reference", None)
        if not callable(resolve_project) or not callable(stable_project_ref):
            return record

        raw_project_ref = str(record.get(project_field) or "").strip()
        if not raw_project_ref:
            return record

        client_field = self._linked_project_client_field(table_name)
        raw_client_id = (
            str(record.get(client_field) or "").strip()
            if client_field and client_field in table_columns
            else ""
        )

        try:
            resolved_project = resolve_project(raw_project_ref, raw_client_id)
        except TypeError:
            resolved_project = resolve_project(raw_project_ref)
        if not resolved_project:
            return record

        normalized_project_ref = str(
            stable_project_ref(resolved_project, raw_project_ref) or ""
        ).strip()
        outbound_updates: dict[str, Any] = {}
        local_updates: dict[str, Any] = {}
        if normalized_project_ref and normalized_project_ref != raw_project_ref:
            outbound_updates[project_field] = normalized_project_ref
            local_updates[project_field] = normalized_project_ref

        if client_field and client_field in table_columns:
            normalized_client_id = raw_client_id
            if raw_client_id and callable(normalize_client_ref):
                try:
                    normalized_client_id = str(normalize_client_ref(raw_client_id) or "").strip()
                except Exception:
                    normalized_client_id = raw_client_id
            elif not raw_client_id:
                normalized_client_id = str(resolved_project.get("client_id") or "").strip()

            if normalized_client_id and normalized_client_id != raw_client_id:
                outbound_updates[client_field] = normalized_client_id
                if table_name not in {"tasks", "quotations"}:
                    local_updates[client_field] = normalized_client_id

        if not outbound_updates and not local_updates:
            return record

        local_id = record.get("id")
        if local_id is not None and local_updates:
            if "last_modified" in table_columns:
                local_updates["last_modified"] = server_now_iso

            table_ref = self._sqlite_table_ref(table_name)
            set_clause = self._sqlite_set_clause_sql(
                list(local_updates.keys()), table_columns=table_columns
            )
            cursor.execute(
                f"UPDATE {table_ref} SET {set_clause} WHERE id = ?",  # nosec B608
                [*local_updates.values(), local_id],
            )
            record.update(local_updates)

        record.update(outbound_updates)

        return record

    @staticmethod
    def _linked_client_only_field(table_name: str) -> str | None:
        return {
            "quotations": "client_id",
        }.get(table_name)

    def _normalize_client_links_for_push(
        self,
        cursor,
        table_name: str,
        record: dict[str, Any],
        table_columns: set[str],
        server_now_iso: str,
    ) -> dict[str, Any]:
        client_field = self._linked_client_only_field(table_name)
        if not client_field or client_field not in table_columns:
            return record

        normalize_client_ref = getattr(self.repo, "_normalize_client_reference", None)
        if not callable(normalize_client_ref):
            return record

        raw_client_id = str(record.get(client_field) or "").strip()
        if not raw_client_id:
            return record

        try:
            normalized_client_id = str(normalize_client_ref(raw_client_id) or "").strip()
        except Exception:
            return record
        if not normalized_client_id or normalized_client_id == raw_client_id:
            return record

        # Quotations keeps local FK values in SQLite but must publish a stable client reference to Mongo.
        record[client_field] = normalized_client_id
        return record

    def _values_equal_for_sync(self, local_value: Any, incoming_value: Any) -> bool:
        """Best-effort value comparison to skip no-op SQLite updates."""
        local_iso = self._to_iso_timestamp(local_value)
        incoming_iso = self._to_iso_timestamp(incoming_value)
        local_dt = self._normalize_datetime(self._parse_iso_datetime(local_iso))
        incoming_dt = self._normalize_datetime(self._parse_iso_datetime(incoming_iso))
        if local_dt is not None and incoming_dt is not None:
            return local_dt == incoming_dt

        if local_value is None:
            local_value = ""
        if incoming_value is None:
            incoming_value = ""

        if isinstance(local_value, bool):
            local_value = int(local_value)
        if isinstance(incoming_value, bool):
            incoming_value = int(incoming_value)

        if isinstance(local_value, int | float) or isinstance(incoming_value, int | float):
            try:
                return abs(float(local_value) - float(incoming_value)) < 1e-9
            except (TypeError, ValueError):
                pass

        if isinstance(local_value, str):
            local_value = local_value.strip()
        if isinstance(incoming_value, str):
            incoming_value = incoming_value.strip()

        return local_value == incoming_value

    def _should_update_local_record(
        self, cursor, table_name: str, local_id: int, incoming: dict[str, Any]
    ) -> bool:
        """Return True only when incoming data differs from local SQLite row."""
        if not incoming:
            return False

        columns = list(incoming.keys())
        table_columns = self._sqlite_table_columns(cursor, table_name)
        table_ref = self._sqlite_table_ref(table_name)
        select_clause = self._sqlite_column_list_sql(columns, table_columns=table_columns)
        select_current_sql = f"SELECT {select_clause} FROM {table_ref} WHERE id = ?"  # nosec B608
        cursor.execute(select_current_sql, (local_id,))
        current_row = cursor.fetchone()
        if not current_row:
            return True

        if hasattr(current_row, "keys"):
            current_map = {col: current_row[col] for col in columns}
        else:
            current_map = dict(zip(columns, current_row, strict=False))

        for column, incoming_value in incoming.items():
            if not self._values_equal_for_sync(current_map.get(column), incoming_value):
                return True
        return False

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(max(0, int(value)))
        units = ["B", "KB", "MB", "GB"]
        unit_idx = 0
        while size >= 1024 and unit_idx < (len(units) - 1):
            size /= 1024.0
            unit_idx += 1
        return f"{size:.1f}{units[unit_idx]}"

    def _invalidate_repository_cache(self, table_name: str | None = None) -> None:
        """Clear repository-level caches so pulled changes become visible immediately."""
        if self.repo is None:
            return

        try:
            if hasattr(self.repo, "invalidate_table_cache"):
                self.repo.invalidate_table_cache(table_name)
                return
        except Exception as e:
            logger.debug("تعذر إبطال cache للجدول %s: %s", table_name, e)

        # Fallback for older Repository implementations.
        table = (table_name or "").strip().lower()
        attr_map = {
            "clients": "_clients_cache",
            "projects": "_projects_cache",
            "services": "_services_cache",
            "accounts": "_accounts_cache",
            "expenses": "_expenses_cache",
        }
        attr_name = attr_map.get(table)
        if not attr_name or not hasattr(self.repo, attr_name):
            return
        try:
            getattr(self.repo, attr_name).invalidate()
        except Exception:
            pass

    def _sqlite_table_exists(self, cursor, table: str) -> bool:
        cached = self._table_exists_cache.get(table)
        if cached is not None:
            return cached
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        exists = bool(cursor.fetchone())
        self._table_exists_cache[table] = exists
        return exists

    def _sqlite_table_columns(self, cursor, table: str) -> set[str]:
        cached = self._table_columns_cache.get(table)
        if cached is not None:
            return cached
        table_ref = self._sqlite_table_ref(table)
        pragma_sql = f"PRAGMA table_info({table_ref})"  # nosec B608
        cursor.execute(pragma_sql)
        columns = {row[1] for row in cursor.fetchall()}
        self._table_columns_cache[table] = columns
        return columns

    def _sqlite_table_ref(self, table: str) -> str:
        return quote_identifier(table, allowed=set(self.TABLES))

    @staticmethod
    def _sqlite_column_ref(column: str, *, allowed: set[str] | None = None) -> str:
        return quote_identifier(column, allowed=allowed)

    def _sqlite_column_list_sql(self, columns: list[str], *, table_columns: set[str]) -> str:
        return ", ".join(quote_identifier_list(columns, allowed=table_columns))

    def _sqlite_set_clause_sql(self, columns: list[str], *, table_columns: set[str]) -> str:
        quoted_columns = quote_identifier_list(columns, allowed=table_columns)
        return ", ".join(f"{column} = ?" for column in quoted_columns)

    def request_realtime_pull(self, table: str | None = None) -> bool:
        """
        Trigger a guarded delta pull in response to realtime events.
        Returns True if a pull was scheduled, False if deduplicated/ignored.
        """
        table_key = table or "__all__"
        now_ms = int(time.monotonic() * 1000)
        last_ms = self._last_realtime_pull_ms.get(table_key, 0)
        if (now_ms - last_ms) < self._realtime_pull_dedupe_ms:
            return False
        self._last_realtime_pull_ms[table_key] = now_ms

        if self._shutdown:
            return False

        if self._is_syncing:
            self._queued_realtime_tables.add(table_key)
            return False

        if not self.is_online:
            return False

        self.force_pull(table if table in self.TABLES else None)
        return True

    def _flush_realtime_pull_queue(self):
        """Run one pull cycle after full sync if realtime events arrived during lock."""
        if self._shutdown or not self._queued_realtime_tables:
            return
        queued = sorted(self._queued_realtime_tables)
        self._queued_realtime_tables.clear()
        logger.debug("⚡ معالجة queued realtime events: %s", queued)
        self.force_pull(None)

    def _normalize_table_key(self, table: str | None) -> str:
        if isinstance(table, str) and table in self.TABLES:
            return table
        return "__all__"

    def schedule_instant_sync(self, table: str | None = None) -> bool:
        """
        Schedule a non-blocking instant sync cycle.
        Uses lightweight delta cycle (push+pull) with burst dedupe to avoid UI freezes.
        """
        if self._shutdown:
            return False

        table_key = self._normalize_table_key(table)
        now_ms = int(time.monotonic() * 1000)

        with self._instant_sync_schedule_lock:
            last_ms = self._last_instant_sync_request_ms.get(table_key, 0)
            if (now_ms - last_ms) < self._instant_sync_dedupe_ms:
                return False
            self._last_instant_sync_request_ms[table_key] = now_ms
            self._instant_sync_pending_tables.add(table_key)

            if self._instant_sync_worker_running:
                return True
            self._instant_sync_worker_running = True

        threading.Thread(
            target=self._instant_sync_worker_loop,
            daemon=True,
            name="unified-instant-sync",
        ).start()
        return True

    def _instant_sync_worker_loop(self):
        """Drain scheduled instant-sync requests in background without blocking UI thread."""
        try:
            # Short batching window to collapse rapid CRUD bursts into one cycle.
            time.sleep(0.06)
            while not self._shutdown:
                with self._instant_sync_schedule_lock:
                    pending = set(self._instant_sync_pending_tables)
                    self._instant_sync_pending_tables.clear()

                if not pending:
                    break

                if not self.is_online:
                    # Offline mode: skip immediate cycle; periodic sync will recover on reconnect.
                    continue

                specific_tables = sorted(t for t in pending if t in self.TABLES)
                run_full_cycle = (
                    "__all__" in pending or not specific_tables or len(specific_tables) > 3
                )
                busy = False

                if run_full_cycle:
                    result = self._run_delta_cycle()
                    busy = result.get("reason") in {"delta_busy", "full_sync_in_progress"}
                else:
                    for table_name in specific_tables:
                        result = self._run_table_reconcile_cycle(table_name)
                        # Fallback for lightweight test repositories that do not expose
                        # full table-reconcile dependencies.
                        if not result.get("success", False) and result.get("reason") not in {
                            "delta_busy",
                            "full_sync_in_progress",
                        }:
                            result = self._run_delta_cycle()
                        if result.get("reason") in {"delta_busy", "full_sync_in_progress"}:
                            busy = True
                            break

                if busy:
                    with self._instant_sync_schedule_lock:
                        self._instant_sync_pending_tables.update(pending)
                    time.sleep(0.15)
                    continue

                # Keep loop cooperative and allow new pending requests to be batched.
                time.sleep(0.02)
        finally:
            restart_worker = False
            with self._instant_sync_schedule_lock:
                self._instant_sync_worker_running = False
                if self._instant_sync_pending_tables and not self._shutdown:
                    self._instant_sync_worker_running = True
                    restart_worker = True
            if restart_worker:
                threading.Thread(
                    target=self._instant_sync_worker_loop,
                    daemon=True,
                    name="unified-instant-sync",
                ).start()

    # ==========================================
    # 🚀 المزامنة الفورية - Real-time Sync
    # ==========================================

    def instant_sync(self, table: str = None):
        """
        ⚡ مزامنة فورية لجدول واحد أو كل الجداول

        Args:
            table: اسم الجدول (اختياري). إذا لم يُحدد، يتم مزامنة كل الجداول
        """
        if self._shutdown or not self.is_online:
            return

        if self._is_syncing:
            if table:
                table_key = table if table in self.TABLES else "__all__"
                self._queued_realtime_tables.add(table_key)
            return

        if table:
            table_key = table if table in self.TABLES else "__all__"
            now_ms = int(time.monotonic() * 1000)
            last_ms = self._last_realtime_pull_ms.get(table_key, 0)
            if (now_ms - last_ms) < self._realtime_pull_dedupe_ms:
                return
            self._last_realtime_pull_ms[table_key] = now_ms

        try:
            with self._lock:
                if table:
                    # بعض الإشارات (مثل accounting) ليست أسماء جداول فعلية.
                    if table not in self.TABLES:
                        self._push_pending_changes()
                        logger.debug("⚡ مزامنة فورية عامة بسبب إشارة %s", table)
                        return

                    # مزامنة جدول واحد
                    self._sync_single_table_to_cloud(table)
                    self._sync_single_table_from_cloud(table)
                    logger.debug("⚡ تم مزامنة %s فوراً", table)
                else:
                    self._push_pending_changes()
                    for table_name in self.TABLES:
                        self._sync_single_table_from_cloud(table_name)
                    logger.debug("⚡ تم مزامنة كل الجداول فوراً")
        except Exception as e:
            logger.debug("خطأ في المزامنة الفورية: %s", e)

    def _sync_single_table_from_cloud(self, table: str):
        """مزامنة جدول واحد من السحابة"""
        if not self.is_online or self.repo is None or self.repo.mongo_db is None:
            return

        if table not in self.TABLES:
            return

        try:
            self._sync_table_from_cloud(table)
        except Exception as e:
            logger.debug("خطأ في مزامنة %s من السحابة: %s", table, e)

    def _sync_single_table_to_cloud(self, table: str):
        """مزامنة جدول واحد فوراً"""
        if not self.is_online or self.repo is None or self.repo.mongo_db is None:
            return

        # ⚡ تجاهل الجداول غير الموجودة
        if table not in self.TABLES:
            return

        try:
            # Reuse the main delta push path so realtime sync keeps the
            # same duplicate handling, delete semantics, and dirty_flag cleanup.
            self.push_local_changes({table})
        except Exception as e:
            logger.debug("تجاهل خطأ مزامنة %s: %s", table, e)

    # ==========================================
    # نظام المزامنة التلقائية الاحترافي
    # ==========================================

    def start_auto_sync(self):
        """🚀 بدء نظام المزامنة التلقائية"""
        if not self._auto_sync_enabled:
            logger.info("ℹ️ المزامنة التلقائية غير مفعلة من الإعدادات")
            return

        logger.info("🚀 بدء نظام المزامنة التلقائية...")
        self._shutdown = False

        # تنظيف أي مؤقتات قديمة قبل إعادة البدء
        for timer_name in (
            "_auto_sync_timer",
            "_quick_sync_timer",
            "_connection_timer",
            "_cloud_pull_timer",
            "_delta_pull_timer",
        ):
            timer = getattr(self, timer_name, None)
            if timer:
                try:
                    timer.stop()
                except Exception:
                    pass
                setattr(self, timer_name, None)

        # 1. مؤقت فحص الاتصال (كل دقيقة)
        self._connection_timer = QTimer(self)
        self._connection_timer.timeout.connect(self._check_connection)
        self._connection_timer.start(self._connection_check_interval)
        # Trigger one non-blocking probe immediately to seed online cache
        # before the first sync-related checks run on the UI thread.
        self._check_connection()

        # 2. مؤقت رفع التغييرات المحلية:
        # Delta Sync ينفذ push+pull بالفعل، لذا نتجنب التكرار عندما يكون Delta أسرع.
        quick_seconds = max(1, self._quick_sync_interval // 1000)
        if self._delta_sync_interval_seconds < quick_seconds:
            self._quick_sync_timer = None
            logger.info(
                "ℹ️ تم تعطيل Quick Push الدوري لأن Delta Sync أسرع (%sث < %sث)",
                self._delta_sync_interval_seconds,
                quick_seconds,
            )
        else:
            self._quick_sync_timer = QTimer(self)
            self._quick_sync_timer.timeout.connect(self._quick_push_changes)
            self._quick_sync_timer.start(self._quick_sync_interval)

        # 3. مؤقت المزامنة الكاملة (كل 5 دقائق)
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.timeout.connect(self._auto_full_sync)
        self._auto_sync_timer.start(self._auto_sync_interval)

        # Safety cloud pull: only when delta sync is relatively slow.
        # With fast delta (<= 10s), this timer causes redundant heavy full-sync load.
        if self._delta_sync_interval_seconds > 10:
            self._cloud_pull_timer = QTimer(self)
            self._cloud_pull_timer.timeout.connect(self._cloud_pull_changes)
            self._cloud_pull_timer.start(CLOUD_PULL_INTERVAL_MS)
        else:
            self._cloud_pull_timer = None
            logger.info(
                "ℹ️ تم تعطيل Cloud Pull الدوري لأن Delta Sync سريع (%s ثانية)",
                self._delta_sync_interval_seconds,
            )

        # 4. مزامنة أولية بعد 5 ثواني
        QTimer.singleShot(5000, self._initial_sync)

        # 5. ⚡ NEW: بدء Delta Sync دوري للمزامنة بين الأجهزة
        self.start_delta_sync(interval_seconds=self._delta_sync_interval_seconds)

        logger.info("⏰ المزامنة الكاملة: كل %s ثانية", self._auto_sync_interval // 1000)
        if self._quick_sync_timer:
            logger.info("⏰ رفع التغييرات: كل %s ثانية", self._quick_sync_interval // 1000)
        else:
            logger.info("⏰ رفع التغييرات: مُعطّل (Delta Sync يغطيه)")
        logger.info("⏰ Delta Sync: كل %s ثانية", self._delta_sync_interval_seconds)

    def stop_auto_sync(self):
        """⏹️ إيقاف نظام المزامنة التلقائية"""
        if self._shutdown and not any(
            (
                self._auto_sync_timer,
                self._quick_sync_timer,
                self._cloud_pull_timer,
                self._connection_timer,
                self._delta_pull_timer,
            )
        ):
            return

        logger.info("⏹️ إيقاف نظام المزامنة التلقائية...")
        self._shutdown = True  # ⚡ تعيين علامة الإغلاق

        # إيقاف المؤقتات بأمان
        try:
            if self._auto_sync_timer:
                try:
                    self._auto_sync_timer.stop()
                except (RuntimeError, AttributeError):
                    pass
                self._auto_sync_timer = None
        except Exception:
            pass

        try:
            if self._quick_sync_timer:
                try:
                    self._quick_sync_timer.stop()
                except (RuntimeError, AttributeError):
                    pass
                self._quick_sync_timer = None
        except Exception:
            pass

        try:
            if self._cloud_pull_timer:
                try:
                    self._cloud_pull_timer.stop()
                except (RuntimeError, AttributeError):
                    pass
                self._cloud_pull_timer = None
        except Exception:
            pass

        try:
            if self._connection_timer:
                try:
                    self._connection_timer.stop()
                except (RuntimeError, AttributeError):
                    pass
                self._connection_timer = None
        except Exception:
            pass

        try:
            if self._delta_pull_timer:
                try:
                    self._delta_pull_timer.stop()
                except (RuntimeError, AttributeError):
                    pass
                self._delta_pull_timer = None
        except Exception:
            pass

        try:
            if self._delta_thread and self._delta_thread.is_alive():
                self._delta_thread_stop.set()
                self._delta_thread.join(timeout=0.5)
        except Exception:
            pass
        self._delta_thread = None

        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline:
            try:
                delta_busy = bool(self._delta_cycle_lock.locked())
            except Exception:
                delta_busy = False
            if not self._is_syncing and not delta_busy:
                break
            time.sleep(0.05)

        logger.info("✅ تم إيقاف نظام المزامنة التلقائية")

    def stop(self):
        self.stop_auto_sync()

    def _probe_online_status(self, *, max_time_ms: int = 800) -> bool:
        """Probe Mongo connectivity with a bounded ping."""
        if self.repo is None:
            return False

        mongo_client = getattr(self.repo, "mongo_client", None)
        mongo_db = getattr(self.repo, "mongo_db", None)
        if mongo_client is None or mongo_db is None:
            return False

        try:
            mongo_client.admin.command("ping", maxTimeMS=max(100, int(max_time_ms)))
            return True
        except TypeError:
            # Backward compatibility for environments that ignore maxTimeMS kwarg.
            try:
                mongo_client.admin.command("ping")
                return True
            except Exception:
                return False
        except Exception:
            return False

    def _set_online_status(self, status: bool) -> bool | None:
        """Update cached online status and return previous cached value."""
        previous_status = None
        current_status = bool(status)
        with self._online_status_lock:
            previous_status = self._last_online_status
            self._last_online_status = current_status
            self._last_online_probe_mono = time.monotonic()
        try:
            if self.repo is not None:
                self.repo.online = current_status
        except Exception:
            pass
        return previous_status

    def _check_connection(self):
        """🔌 Non-blocking connection probe to avoid UI freezes."""
        if self._shutdown:  # ⚡ تجاهل إذا تم الإغلاق
            return

        with self._connection_probe_lock:
            if self._connection_probe_in_flight:
                return
            self._connection_probe_in_flight = True

        def worker():
            try:
                current_status = self._probe_online_status(max_time_ms=700)
                previous_status = self._set_online_status(current_status)

                # إرسال إشارة عند تغيير الحالة فقط
                if current_status != previous_status:
                    try:
                        if not self._shutdown:
                            self.connection_changed.emit(current_status)
                    except RuntimeError:
                        return  # Qt object deleted

                    if current_status:
                        logger.info("🟢 تم استعادة الاتصال")
                        # لا نطلق Full Sync فوري في أول تشغيل.
                        if previous_status is False:
                            self._run_full_sync_async()
                    else:
                        logger.warning("🔴 انقطع الاتصال - العمل في وضع Offline")
            except Exception:
                # تجاهل أخطاء probe
                pass
            finally:
                with self._connection_probe_lock:
                    self._connection_probe_in_flight = False

        threading.Thread(target=worker, daemon=True, name="unified-connection-check").start()

    def _initial_sync(self):
        """🚀 المزامنة الأولية عند بدء التشغيل - تفاضلية للسرعة"""
        if self._shutdown:
            return

        if not self.is_online:
            logger.info("📴 لا يوجد اتصال - العمل بالبيانات المحلية")
            return

        logger.info("🚀 بدء المزامنة الأولية...")
        if not self._run_full_sync_async(source="initial"):
            logger.info("⏭️ تم تخطي المزامنة الأولية لأن مزامنة أخرى شغالة بالفعل")

    def _auto_full_sync(self):
        """🔄 المزامنة التلقائية - تفاضلية للسرعة"""
        if self._shutdown or self._is_syncing or not self.is_online:
            return

        if self._delta_sync_interval_seconds <= 10:
            now_mono = time.monotonic()
            delta_is_active = (now_mono - self._last_delta_cycle_mono) <= max(
                40.0, float(self._delta_sync_interval_seconds) * 6.0
            )
            if delta_is_active and self._last_full_sync_at:
                age_seconds = max(0.0, (datetime.now() - self._last_full_sync_at).total_seconds())
                if age_seconds < float(self._min_full_sync_when_delta_active_seconds):
                    logger.debug(
                        "⏭️ skip periodic full sync while delta is healthy | age=%.1fs threshold=%ss",
                        age_seconds,
                        self._min_full_sync_when_delta_active_seconds,
                    )
                    return

        self._run_full_sync_async()

    def _quick_push_changes(self):
        """⚡ رفع التغييرات المحلية بسرعة"""
        if self._shutdown or self._is_syncing or not self.is_online:
            return

        try:
            # ⚡ إنشاء cursor جديد لتجنب Recursive cursor error
            cursor = self.repo.get_cursor()
            has_pending = False

            try:
                for table in self.TABLES:
                    try:
                        table_ref = self._sqlite_table_ref(table)
                        pending_count_sql = f"SELECT COUNT(*) FROM {table_ref} WHERE sync_status != 'synced' OR sync_status IS NULL"  # nosec B608
                        cursor.execute(pending_count_sql)
                        count = cursor.fetchone()[0]
                        if count > 0:
                            has_pending = True
                            break
                    except Exception:
                        # فشل فحص العنصر
                        pass
            finally:
                cursor.close()  # ⚡ إغلاق الـ cursor

            if has_pending:

                def push_thread():
                    if self._shutdown:
                        return
                    try:
                        with self._lock:
                            self._push_pending_changes()
                        logger.debug("⚡ تم رفع التغييرات المحلية")
                    except Exception as e:
                        logger.error("❌ فشل رفع التغييرات: %s", e)

                threading.Thread(target=push_thread, daemon=True).start()

        except Exception as e:
            logger.debug("خطأ في فحص التغييرات: %s", e)

    def set_auto_sync_interval(self, minutes: int):
        """⏰ تغيير فترة المزامنة التلقائية"""
        self._auto_sync_interval = minutes * 60 * 1000
        if self._auto_sync_timer:
            self._auto_sync_timer.setInterval(self._auto_sync_interval)
        logger.info("⏰ تم تغيير فترة المزامنة إلى %s دقيقة", minutes)

    @property
    def is_online(self) -> bool:
        """التحقق من الاتصال مع كاش سريع لتفادي حظر واجهة المستخدم."""
        if self.repo is None:
            return False

        mongo_client = getattr(self.repo, "mongo_client", None)
        mongo_db = getattr(self.repo, "mongo_db", None)
        if mongo_client is None or mongo_db is None:
            self._set_online_status(False)
            return False

        now_mono = time.monotonic()
        with self._online_status_lock:
            cached_status = self._last_online_status
            cache_age = now_mono - self._last_online_probe_mono

        # Fast path: recently probed status.
        if cached_status is not None and cache_age <= self._online_status_cache_ttl_seconds:
            return bool(cached_status)

        is_ui_thread = threading.current_thread() is threading.main_thread()
        if is_ui_thread:
            # Never block UI thread on ping.
            self._check_connection()
            fallback = bool(getattr(self.repo, "online", False))
            if cached_status is None:
                return fallback
            return bool(cached_status or fallback)

        # Background threads can perform bounded probe.
        current_status = self._probe_online_status(max_time_ms=900)
        self._set_online_status(current_status)
        return bool(current_status)

    def _wait_for_connection(self, timeout: int = 10) -> bool:
        """⚡ انتظار اتصال MongoDB مع timeout"""
        import time

        waited = 0
        while not self.is_online and waited < timeout:
            time.sleep(0.5)
            waited += 0.5
        return self.is_online

    def _run_full_sync_async(self, source: str = "background") -> bool:
        with self._full_sync_dispatch_lock:
            if (
                self._shutdown
                or self._is_syncing
                or self._full_sync_thread_in_flight
                or not self.is_online
            ):
                return False
            self._full_sync_thread_in_flight = True

        def worker():
            if self._shutdown:
                return
            try:
                result = self.full_sync_from_cloud()
                if source == "initial":
                    if result.get("success"):
                        logger.info("✅ المزامنة الأولية: تم توحيد البيانات بالكامل")
                    else:
                        logger.info(
                            "⏭️ تم تخطي المزامنة الأولية: %s",
                            result.get("reason", "busy"),
                        )
            except Exception as e:
                logger.debug("خطأ في المزامنة الخلفية: %s", e)
            finally:
                with self._full_sync_dispatch_lock:
                    self._full_sync_thread_in_flight = False

        threading.Thread(target=worker, daemon=True).start()
        return True

    def _cloud_pull_changes(self):
        if self._shutdown or not self.is_online:
            return
        if self._is_syncing:
            return
        # If delta sync is fast, avoid redundant forced full syncs.
        if self._delta_sync_interval_seconds <= 10:
            return
        if self._last_full_sync_at:
            if (datetime.now() - self._last_full_sync_at).total_seconds() < 30:
                return
        self._run_full_sync_async()

    def full_sync_from_cloud(self) -> dict[str, Any]:
        """
        مزامنة كاملة من السحابة - MongoDB هو المصدر الوحيد
        يحذف البيانات المحلية غير الموجودة في السحابة
        """
        # ⚡ فحص الإغلاق أولاً
        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        # ⚡ انتظار الاتصال أولاً
        if not self._wait_for_connection(timeout=10):
            logger.warning("غير متصل - لا يمكن المزامنة من السحابة")
            return {"success": False, "reason": "offline"}

        if self._is_syncing:
            return {"success": False, "reason": "already_syncing"}

        # ⚡ فحص فعلي أن MongoDB client لا يزال متاحاً
        if self.repo is None or self.repo.mongo_client is None or self.repo.mongo_db is None:
            return {"success": False, "reason": "no_mongo_client"}

        try:
            self.repo.mongo_client.admin.command("ping")
        except Exception:
            logger.debug("MongoDB client مغلق - تخطي المزامنة الكاملة")
            return {"success": False, "reason": "mongo_client_closed"}

        self._is_syncing = True
        self._last_full_sync_at = datetime.now()
        self.sync_started.emit()

        results = {"success": True, "tables": {}, "total_synced": 0, "total_deleted": 0}
        changed_tables: set[str] = set()

        try:
            with self._lock:
                # 1. رفع التغييرات المحلية أولاً
                self._push_pending_changes()

                # 2. مزامنة المستخدمين
                self._sync_users_from_cloud()

                # 3. مزامنة كل جدول
                for table in self.TABLES:
                    try:
                        stats = self._sync_table_from_cloud(table)
                        results["tables"][table] = stats
                        results["total_synced"] += stats.get("synced", 0)
                        results["total_deleted"] += stats.get("deleted", 0)
                        if (
                            stats.get("inserted", 0) > 0
                            or stats.get("updated", 0) > 0
                            or stats.get("deleted", 0) > 0
                        ):
                            changed_tables.add(table)
                    except Exception as e:
                        logger.error("❌ خطأ في مزامنة %s: %s", table, e)
                        results["tables"][table] = {"error": str(e)}

            logger.info("✅ اكتملت المزامنة: %s سجل", results["total_synced"])
            self._update_sync_metrics(success=True, records_synced=results["total_synced"])
            self.sync_completed.emit(results)

            # ⚡ إعادة حساب أرصدة الحسابات النقدية بعد المزامنة
            try:
                accounting_tables = {"accounts", "payments", "expenses", "journal_entries"}
                if changed_tables.intersection(accounting_tables):
                    from services.accounting_service import AccountingService

                    # إبطال الـ cache أولاً
                    AccountingService._hierarchy_cache = None
                    AccountingService._hierarchy_cache_time = 0
                    logger.info(
                        "📊 تم إبطال cache الحسابات بعد تغيّر بيانات محاسبية - سيتم إعادة الحساب عند فتح تاب المحاسبة"
                    )
            except Exception as e:
                logger.warning("⚠️ فشل إبطال cache الحسابات: %s", e)

            # ⚡ إرسال إشارات تحديث البيانات لتحديث الواجهة
            try:
                from core.signals import app_signals

                for table_name in sorted(changed_tables):
                    app_signals.emit_ui_data_changed(table_name)
                if changed_tables:
                    logger.info("📢 تم إرسال إشارات تحديث الواجهة للجداول المتغيرة فقط")
            except Exception as e:
                logger.warning("⚠️ فشل إرسال إشارات التحديث: %s", e)

        except Exception as e:
            logger.error("❌ خطأ في المزامنة الكاملة: %s", e)
            results["success"] = False
            results["error"] = str(e)
            self._update_sync_metrics(success=False, records_synced=0)
            self.sync_error.emit(str(e))

        finally:
            self._is_syncing = False
            self._flush_realtime_pull_queue()

        return results

    def _sync_table_from_cloud(self, table_name: str) -> dict[str, int]:
        """
        مزامنة جدول واحد من السحابة مع منع التكرارات
        """
        stats = {"synced": 0, "inserted": 0, "updated": 0, "deleted": 0, "linked": 0}

        try:
            # ⚡ فحص الاتصال قبل استخدام MongoDB
            if self._shutdown:
                return stats

            if self.repo is None or not self.repo.online:
                return stats

            # ⚡ فحص أن MongoDB client لا يزال متاحاً
            if self.repo.mongo_db is None or self.repo.mongo_client is None:
                return stats

            # ⚡ فحص فعلي أن الـ client لم يُغلق
            try:
                # محاولة ping للتأكد من أن الاتصال فعال
                self.repo.mongo_client.admin.command("ping")
            except Exception:
                logger.debug(
                    "تم تخطي مزامنة %s - MongoDB client مغلق أو غير متاح",
                    table_name,
                )
                return stats

            # جلب البيانات من السحابة
            try:
                cloud_query: dict[str, Any] = {}
                if table_name == "notifications":
                    cloud_query = self._merge_query_with_notification_filter(cloud_query)
                cloud_data = list(self.repo.mongo_db[table_name].find(cloud_query))
            except Exception as mongo_err:
                error_msg = str(mongo_err)
                if (
                    "Cannot use MongoClient after close" in error_msg
                    or "InvalidOperation" in error_msg
                ):
                    logger.debug("تم تخطي مزامنة %s - MongoDB client مغلق", table_name)
                    return stats
                raise

            if not cloud_data:
                logger.info("لا توجد بيانات في %s", table_name)
                return stats

            # ⚡ إنشاء cursor جديد لتجنب Recursive cursor error
            cursor = self.repo.get_cursor()
            conn = self.repo.sqlite_conn
            unique_field = self.UNIQUE_FIELDS.get(table_name, "name")

            try:
                # الحصول على أعمدة الجدول
                table_columns = self._sqlite_table_columns(cursor, table_name)

                # جمع كل الـ mongo_ids من السحابة
                cloud_mongo_ids = set()
                logo_clients = 0
                logo_payload_bytes = 0

                for i, cloud_item in enumerate(cloud_data):
                    self.sync_progress.emit(table_name, i + 1, len(cloud_data))

                    mongo_id = str(cloud_item["_id"])
                    cloud_mongo_ids.add(mongo_id)
                    unique_value = cloud_item.get(unique_field)
                    remote_sync_status = str(cloud_item.get("sync_status") or "").lower()
                    remote_is_deleted = bool(cloud_item.get("is_deleted", False)) or (
                        remote_sync_status == "deleted"
                    )

                    # تحضير البيانات
                    item_data = self._prepare_cloud_data(cloud_item, table_name=table_name)
                    if item_data.pop("__skip_sync__", False):
                        logger.warning("⚠️ تم تخطي سجل %s غير صالح من السحابة", table_name)
                        continue
                    item_data["_mongo_id"] = mongo_id
                    item_data["sync_status"] = "synced"

                    if table_name == "clients":
                        raw_logo = cloud_item.get("logo_data")
                        has_logo = bool(cloud_item.get("has_logo", False) or raw_logo)
                        if has_logo:
                            logo_clients += 1
                            if isinstance(raw_logo, str):
                                logo_payload_bytes += len(raw_logo.encode("utf-8"))

                    # البحث عن السجل المحلي
                    local_id = self._find_local_record(
                        cursor, table_name, mongo_id, unique_field, unique_value, table_columns
                    )

                    # تصفية الحقول
                    filtered = {k: v for k, v in item_data.items() if k in table_columns}

                    if local_id:
                        if not remote_is_deleted:
                            local_sync_status, local_is_deleted = self._get_local_sync_state(
                                cursor, table_name, local_id
                            )
                            if local_is_deleted or local_sync_status == "deleted":
                                logger.debug(
                                    "⏭️ skip resurrecting locally deleted row %s/%s during cloud sync",
                                    table_name,
                                    local_id,
                                )
                                continue
                        # تحديث السجل فقط عند وجود فرق حقيقي لتقليل الحمل على SQLite والواجهة.
                        if self._should_update_local_record(cursor, table_name, local_id, filtered):
                            self._update_record(cursor, table_name, local_id, filtered)
                            stats["updated"] += 1
                            stats["synced"] += 1
                    else:
                        # إدراج سجل جديد
                        self._insert_record(cursor, table_name, filtered)
                        stats["inserted"] += 1
                        stats["synced"] += 1

                # حذف السجلات المحلية غير الموجودة في السحابة
                deleted = self._delete_orphan_records(cursor, table_name, cloud_mongo_ids)
                stats["deleted"] = deleted

                conn.commit()
                if stats["inserted"] > 0 or stats["updated"] > 0 or stats["deleted"] > 0:
                    self._invalidate_repository_cache(table_name)
                if stats["inserted"] > 0 or stats["updated"] > 0 or stats["deleted"] > 0:
                    logger.info(
                        "✅ %s: +%s ~%s -%s",
                        table_name,
                        stats["inserted"],
                        stats["updated"],
                        stats["deleted"],
                    )
                if table_name == "clients" and logo_clients > 0:
                    if self._lazy_logo_enabled:
                        logger.info(
                            "📷 clients: %s عميل لديه شعار (metadata synced - lazy mode)",
                            logo_clients,
                        )
                        if logo_payload_bytes > 0:
                            logger.debug(
                                "📷 clients: تم تخطي تحميل payload بحجم تقريبي %s أثناء full sync",
                                self._format_bytes(logo_payload_bytes),
                            )
                    else:
                        logger.info(
                            "📷 clients: تم تحميل شعارات %s عميل (حجم تقريبي %s)",
                            logo_clients,
                            self._format_bytes(logo_payload_bytes),
                        )

            finally:
                # ⚡ إغلاق الـ cursor
                try:
                    cursor.close()
                except Exception:
                    pass

        except Exception as e:
            logger.error("❌ خطأ في مزامنة %s: %s", table_name, e)
            # ⚡ إغلاق الـ cursor في حالة الخطأ
            try:
                cursor.close()
            except Exception:
                pass

        return stats

    def _find_local_record(
        self,
        cursor,
        table_name: str,
        mongo_id: str,
        unique_field: str,
        unique_value: Any,
        table_columns: set,
    ) -> int | None:
        """
        البحث عن السجل المحلي بعدة طرق لمنع التكرارات

        ⚡ NEW: Force Overwrite Logic for Projects
        - If local record exists with same ID but different _mongo_id → DELETE local, INSERT remote
        - Server data is the Single Source of Truth
        """
        try:
            table_ref = self._sqlite_table_ref(table_name)

            # 1. البحث بـ _mongo_id أولاً
            mongo_lookup_sql = f"SELECT id FROM {table_ref} WHERE _mongo_id = ?"  # nosec B608
            cursor.execute(mongo_lookup_sql, (mongo_id,))
            row = cursor.fetchone()
            if row:
                return row[0]

            if table_name == "notifications":
                return None

            # 2. البحث بالحقل الفريد - وتحديث الـ mongo_id
            if unique_value and unique_field in table_columns:
                unique_field_ref = self._sqlite_column_ref(unique_field, allowed=table_columns)
                unique_lookup_sql = f"SELECT id, _mongo_id FROM {table_ref} WHERE {unique_field_ref} = ?"  # nosec B608
                cursor.execute(
                    unique_lookup_sql,
                    (unique_value,),
                )
                row = cursor.fetchone()
                if row:
                    local_id = row[0]
                    existing_mongo_id = row[1]

                    # ⚡ FORCE OVERWRITE LOGIC (Projects only)
                    if (
                        table_name == "projects"
                        and existing_mongo_id
                        and existing_mongo_id != mongo_id
                    ):
                        # ID collision detected: local record has different _mongo_id
                        # This means it's a different record, just unlucky collision
                        # DELETE local record to allow remote data to be inserted
                        logger.warning(
                            "🔥 [FORCE OVERWRITE] Project ID collision detected: "
                            "local_id=%s, local_mongo_id=%s, remote_mongo_id=%s. "
                            "Deleting local record to prioritize server data.",
                            local_id,
                            existing_mongo_id,
                            mongo_id,
                        )
                        safe_print(
                            f"⚠️ [FORCE OVERWRITE] حذف مشروع محلي (ID={local_id}) "
                            f"لإفساح المجال لبيانات السيرفر (mongo_id={mongo_id})"
                        )

                        # Delete the local record
                        delete_local_sql = f"DELETE FROM {table_ref} WHERE id = ?"  # nosec B608
                        cursor.execute(delete_local_sql, (local_id,))

                        # Return None to signal that a new record should be inserted
                        return None

                    # ⚡ إصلاح: تحديث الـ mongo_id إذا كان مختلف (للجداول الأخرى)
                    if existing_mongo_id != mongo_id:
                        update_mongo_id_sql = (
                            f"UPDATE {table_ref} SET _mongo_id = ? WHERE id = ?"  # nosec B608
                        )
                        cursor.execute(
                            update_mongo_id_sql,
                            (mongo_id, local_id),
                        )
                    return local_id
        except Exception as e:
            logger.debug("خطأ في البحث عن السجل: %s", e)

        return None

    def _get_local_sync_state(self, cursor, table_name: str, local_id: int) -> tuple[str, bool]:
        try:
            table_ref = self._sqlite_table_ref(table_name)
            state_lookup_sql = (
                f"SELECT sync_status, is_deleted FROM {table_ref} WHERE id = ?"  # nosec B608
            )
            cursor.execute(state_lookup_sql, (local_id,))
            row = cursor.fetchone()
            if not row:
                return "", False
            return str(row[0] or "").lower(), bool(row[1])
        except Exception:
            return "", False

    def _delete_orphan_records(self, cursor, table_name: str, valid_mongo_ids: set) -> int:
        """
        حذف السجلات المحلية غير الموجودة في السحابة
        (السجلات التي لها _mongo_id لكنه غير موجود في السحابة)
        """
        if not valid_mongo_ids:
            return 0

        # جلب السجلات المحلية التي لها _mongo_id
        table_ref = self._sqlite_table_ref(table_name)
        local_records_sql = (
            f"SELECT id, _mongo_id FROM {table_ref} WHERE _mongo_id IS NOT NULL"  # nosec B608
        )
        cursor.execute(local_records_sql)
        local_records = cursor.fetchall()

        deleted = 0
        for row in local_records:
            local_id = row[0]
            local_mongo_id = row[1]

            if local_mongo_id and local_mongo_id not in valid_mongo_ids:
                delete_orphan_sql = f"DELETE FROM {table_ref} WHERE id = ?"  # nosec B608
                cursor.execute(delete_orphan_sql, (local_id,))
                deleted += 1
                logger.debug("حذف سجل يتيم: %s/%s", table_name, local_id)

        return deleted

    def _prepare_cloud_data(self, data: dict, table_name: str | None = None) -> dict:
        """تحضير بيانات السحابة للحفظ محلياً."""
        item = dict(data)
        item.pop("_id", None)
        item.pop("id", None)

        if table_name == "clients":
            raw_logo = data.get("logo_data")
            has_logo = bool(data.get("has_logo", False) or raw_logo)
            item["has_logo"] = 1 if has_logo else 0

            logo_last_synced = data.get("logo_last_synced") or data.get("last_modified")
            if hasattr(logo_last_synced, "isoformat"):
                item["logo_last_synced"] = logo_last_synced.isoformat()
            elif logo_last_synced is not None:
                item["logo_last_synced"] = str(logo_last_synced)
            else:
                item["logo_last_synced"] = None

            if self._lazy_logo_enabled:
                # Lazy mode: keep metadata only and avoid writing heavy blob in normal pulls/full sync.
                item.pop("logo_data", None)
                if not has_logo:
                    item["logo_data"] = None
                if raw_logo:
                    logger.debug(
                        "📷 [%s] lazy mode: skipped logo_data payload (%s chars)",
                        data.get("name", "غير معروف"),
                        len(str(raw_logo)),
                    )
            elif raw_logo:
                item["logo_data"] = raw_logo
                logger.debug(
                    "📷 [%s] logo_data payload synced (%s chars)",
                    data.get("name", "غير معروف"),
                    len(str(raw_logo)),
                )
        elif table_name == "projects":
            # Guard against partially broken cloud payloads that previously caused
            # validation crashes in SQLite readers.
            name = str(item.get("name") or "").strip()
            client_id = str(item.get("client_id") or "").strip()
            if not name or not client_id:
                item["__skip_sync__"] = True
                return item

            item["name"] = name
            item["client_id"] = client_id
            item["status"] = str(item.get("status") or "نشط")
            item["currency"] = str(item.get("currency") or "EGP")
            item["status_manually_set"] = self._to_safe_bool_int(item.get("status_manually_set"))
            item["is_retainer"] = self._to_safe_bool_int(item.get("is_retainer"))
            item["sequence_number"] = self._to_safe_int(item.get("sequence_number"), 0)

            for numeric_field in [
                "subtotal",
                "discount_rate",
                "discount_amount",
                "tax_rate",
                "tax_amount",
                "total_amount",
                "total_estimated_cost",
                "estimated_profit",
                "profit_margin",
            ]:
                item[numeric_field] = self._to_safe_float(item.get(numeric_field), 0.0)

            if item.get("items") is None:
                item["items"] = []
            if item.get("milestones") is None:
                item["milestones"] = []
            if not item.get("contract_type"):
                item["contract_type"] = "مرة واحدة"
        elif table_name == "tasks":
            normalize_related_client_ref = getattr(self.repo, "_normalize_related_client_ref", None)
            raw_related_client = str(item.get("related_client_id") or "").strip()
            if raw_related_client and callable(normalize_related_client_ref):
                try:
                    normalized_related_client = str(
                        normalize_related_client_ref(raw_related_client) or ""
                    ).strip()
                except Exception:
                    normalized_related_client = ""
                item["related_client_id"] = normalized_related_client or None
        elif table_name == "quotations":
            normalize_local_client_ref = getattr(
                self.repo, "_normalize_local_client_reference", None
            )
            raw_client_id = str(item.get("client_id") or "").strip()
            if raw_client_id and callable(normalize_local_client_ref):
                try:
                    normalized_client_id = str(
                        normalize_local_client_ref(raw_client_id) or ""
                    ).strip()
                except Exception:
                    normalized_client_id = ""
                if not normalized_client_id:
                    item["__skip_sync__"] = True
                    return item
                item["client_id"] = normalized_client_id

        # تحويل التواريخ
        date_fields = [
            "created_at",
            "last_modified",
            "date",
            "issue_date",
            "valid_until",
            "due_date",
            "expiry_date",
            "start_date",
            "end_date",
            "last_attempt",
            "expires_at",
            "last_login",
            "conversion_date",
            "sent_date",
            "viewed_date",
            "response_date",
        ]
        for field in date_fields:
            if field in item and hasattr(item[field], "isoformat"):
                item[field] = item[field].isoformat()

        # تحويل القوائم والكائنات إلى JSON
        json_fields = ["items", "lines", "data", "milestones", "tags"]
        for field in json_fields:
            if field in item and isinstance(item[field], list | dict):
                item[field] = json.dumps(item[field], ensure_ascii=False)

        # التأكد من الحقول المطلوبة
        now = datetime.now().isoformat()
        created_at = self._to_iso_timestamp(item.get("created_at"))
        last_modified = self._to_iso_timestamp(item.get("last_modified"))
        fallback_timestamp = (
            self._to_iso_timestamp(item.get("date"))
            or self._to_iso_timestamp(item.get("issue_date"))
            or self._to_iso_timestamp(item.get("start_date"))
        )
        if not created_at:
            created_at = last_modified or fallback_timestamp or now
        if not last_modified:
            # Use deterministic fallback to avoid touching unchanged rows every full sync.
            last_modified = created_at or fallback_timestamp or now
        item["created_at"] = created_at
        item["last_modified"] = last_modified

        return item

    def _update_record(self, cursor, table_name: str, local_id: int, data: dict):
        """تحديث سجل محلي"""
        if not data:
            return

        table_ref = self._sqlite_table_ref(table_name)
        table_columns = self._sqlite_table_columns(cursor, table_name)
        set_clause = self._sqlite_set_clause_sql(list(data.keys()), table_columns=table_columns)
        values = list(data.values()) + [local_id]
        update_sql = f"UPDATE {table_ref} SET {set_clause} WHERE id = ?"  # nosec B608
        cursor.execute(update_sql, values)

    def _insert_record(self, cursor, table_name: str, data: dict):
        """إدراج سجل جديد مع التعامل مع التكرارات"""
        if not data:
            return

        table_ref = self._sqlite_table_ref(table_name)
        table_columns = self._sqlite_table_columns(cursor, table_name)

        # ⚡ معالجة خاصة للدفعات - فحص التكرار بـ (project_id + date + amount)
        if table_name == "payments":
            project_id = data.get("project_id")
            date = data.get("date", "")
            amount = data.get("amount", 0)
            date_short = str(date)[:10] if date else ""

            if project_id and amount:
                try:
                    cursor.execute(
                        """SELECT id FROM payments
                           WHERE project_id = ? AND amount = ? AND date LIKE ?""",
                        (project_id, amount, f"{date_short}%"),
                    )
                    existing = cursor.fetchone()
                    if existing:
                        # تحديث بدلاً من إدراج
                        self._update_record(cursor, table_name, existing[0], data)
                        logger.debug("تم تحديث دفعة موجودة: %s - %s", project_id, amount)
                        return
                except Exception:
                    pass

        if table_name == "expenses":
            project_id = str(data.get("project_id") or "").strip()
            date = data.get("date", "")
            date_short = str(date)[:10] if date else ""
            try:
                amount = round(float(data.get("amount", 0) or 0.0), 2)
            except (TypeError, ValueError):
                amount = 0.0
            amount_min = amount - 0.01
            amount_max = amount + 0.01
            account_id = str(data.get("account_id") or "").strip()
            payment_account_id = str(data.get("payment_account_id") or account_id).strip()
            category_norm = " ".join(str(data.get("category", "") or "").split()).strip().casefold()
            description_norm = (
                " ".join(str(data.get("description", "") or "").split()).strip().casefold()
            )

            if project_id and amount:
                try:
                    cursor.execute(
                        """
                        SELECT id, category, description
                        FROM expenses
                        WHERE COALESCE(project_id, '') = ?
                          AND amount >= ? AND amount <= ?
                          AND date LIKE ?
                          AND COALESCE(account_id, '') = ?
                          AND COALESCE(payment_account_id, '') = ?
                        ORDER BY id ASC
                        """,
                        (
                            project_id,
                            amount_min,
                            amount_max,
                            f"{date_short}%",
                            account_id,
                            payment_account_id,
                        ),
                    )
                    existing_rows = cursor.fetchall()
                    for row in existing_rows:
                        row_dict = dict(row)
                        row_category = (
                            " ".join(str(row_dict.get("category", "") or "").split())
                            .strip()
                            .casefold()
                        )
                        row_description = (
                            " ".join(str(row_dict.get("description", "") or "").split())
                            .strip()
                            .casefold()
                        )
                        if row_category == category_norm and row_description == description_norm:
                            self._update_record(cursor, table_name, row_dict["id"], data)
                            logger.debug("تم تحديث مصروف موجود: %s - %s", project_id, amount)
                            return
                except Exception:
                    pass

        columns = self._sqlite_column_list_sql(list(data.keys()), table_columns=table_columns)
        placeholders = ", ".join(["?" for _ in data])

        try:
            insert_sql = (
                f"INSERT INTO {table_ref} ({columns}) VALUES ({placeholders})"  # nosec B608
            )
            cursor.execute(insert_sql, list(data.values()))
        except Exception as e:
            # في حالة UNIQUE constraint - نحاول التحديث بدلاً من الإدراج
            if "UNIQUE constraint" in str(e):
                # البحث عن السجل الموجود وتحديثه
                unique_field = self.UNIQUE_FIELDS.get(table_name, "name")
                unique_value = data.get(unique_field)
                mongo_id = data.get("_mongo_id")

                if unique_value:
                    try:
                        unique_field_ref = self._sqlite_column_ref(
                            unique_field, allowed=table_columns
                        )
                        duplicate_lookup_sql = (
                            f"SELECT id FROM {table_ref} WHERE {unique_field_ref} = ?"  # nosec B608
                        )
                        # تحديث السجل الموجود
                        cursor.execute(duplicate_lookup_sql, (unique_value,))
                        row = cursor.fetchone()
                        if row:
                            self._update_record(cursor, table_name, row[0], data)
                            logger.debug("تم تحديث السجل المكرر: %s", unique_value)
                            return
                    except Exception:
                        pass

                # محاولة البحث بـ mongo_id
                if mongo_id:
                    try:
                        mongo_lookup_sql = (
                            f"SELECT id FROM {table_ref} WHERE _mongo_id = ?"  # nosec B608
                        )
                        cursor.execute(mongo_lookup_sql, (mongo_id,))
                        row = cursor.fetchone()
                        if row:
                            self._update_record(cursor, table_name, row[0], data)
                            return
                    except Exception:
                        pass

                # تجاهل الخطأ إذا فشل كل شيء
                logger.debug("تجاهل سجل مكرر في %s", table_name)
            else:
                raise

    def _push_pending_changes(self):
        """
        رفع التغييرات المحلية المعلقة للسحابة قبل السحب
        """
        # ⚡ فحص الاتصال والإغلاق
        if self._shutdown:
            return

        if not self.is_online:
            return

        if self.repo is None or self.repo.mongo_db is None or self.repo.mongo_client is None:
            logger.debug("تم تخطي رفع التغييرات - MongoDB client غير متاح")
            return

        logger.info("📤 جاري رفع التغييرات المحلية...")
        try:
            self.push_local_changes()
        except Exception as e:
            logger.error("❌ خطأ في رفع التغييرات المحلية: %s", e)

    def _push_table_changes(self, table_name: str):
        """رفع تغييرات جدول واحد"""
        try:
            if self._shutdown:
                return
            if self.repo is None or not self.repo.online:
                return
            if self.repo.mongo_db is None or self.repo.mongo_client is None:
                logger.debug("تم تخطي رفع %s - MongoDB client غير متاح", table_name)
                return

            self.push_local_changes({table_name})
        except Exception as e:
            logger.error("❌ خطأ في رفع %s: %s", table_name, e)

    def _prepare_data_for_cloud(self, data: dict) -> dict:
        """تحضير البيانات للرفع للسحابة"""
        clean = {k: v for k, v in data.items() if k not in ["id", "_mongo_id", "sync_status"]}

        # ⚡ التعامل مع logo_data
        # إذا كان logo_data فارغ و logo_path فارغ = المستخدم حذف الصورة صراحة
        # إذا كان logo_data فارغ و logo_path موجود = لا نريد الكتابة فوق السحابة
        logo_data_value = clean.get("logo_data", None)
        logo_path_value = clean.get("logo_path", None)

        if "logo_data" in clean:
            if logo_data_value:
                # صورة جديدة - رفعها للسحابة
                logger.debug("📷 رفع logo_data (%s حرف) للسحابة", len(logo_data_value))
            elif not logo_path_value:
                # logo_data فارغ و logo_path فارغ = حذف صريح للصورة
                clean["logo_data"] = ""  # إرسال قيمة فارغة صريحة للحذف
                logger.debug("🗑️ حذف logo_data من السحابة (حذف صريح)")
            else:
                # logo_data فارغ لكن logo_path موجود = لا نريد الكتابة فوق السحابة
                del clean["logo_data"]
                logger.debug("📷 تم تجاهل logo_data الفارغ (لن يتم الكتابة فوق السحابة)")

        if "logo_path" in clean and not clean["logo_path"]:
            # إذا كان logo_path فارغ، نرسل قيمة فارغة صريحة
            clean["logo_path"] = ""

        # تحويل التواريخ
        for field in [
            "date",
            "issue_date",
            "due_date",
            "expiry_date",
            "start_date",
            "end_date",
        ]:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = datetime.fromisoformat(clean[field].replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

        # توحيد الطوابع الزمنية كنص ISO لتسهيل المقارنة بالـ watermark.
        now_iso = datetime.now().isoformat()
        created_at = clean.get("created_at")
        if not created_at:
            clean["created_at"] = now_iso
        else:
            clean["created_at"] = self._to_iso_timestamp(created_at)

        last_modified = clean.get("last_modified")
        if not last_modified:
            clean["last_modified"] = now_iso
        else:
            clean["last_modified"] = self._to_iso_timestamp(last_modified)

        # تحويل JSON strings إلى objects
        for field in ["items", "lines", "data", "milestones"]:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = json.loads(clean[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        return clean

    def _sync_users_from_cloud(self):
        """مزامنة المستخدمين ثنائية الاتجاه (من وإلى السحابة)"""
        try:
            mongo_db = getattr(self.repo, "mongo_db", None)
            users_collection = getattr(mongo_db, "users", None) if mongo_db is not None else None
            if users_collection is None:
                logger.info("ℹ️ تخطي مزامنة المستخدمين: MongoDB users collection غير متاحة")
                return

            # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
            cursor = self.repo.get_cursor()
            conn = self.repo.sqlite_conn

            try:
                # === 1. رفع المستخدمين المحليين الجدد/المعدلين إلى السحابة ===
                logger.info("📤 جاري رفع المستخدمين المحليين إلى السحابة...")
                cursor.execute(
                    """
                    SELECT * FROM users
                    WHERE sync_status IN ('new_offline', 'modified_offline', 'pending')
                       OR _mongo_id IS NULL
                """
                )
                local_pending = cursor.fetchall()

                uploaded_count = 0
                for row in local_pending:
                    user_data = dict(row)
                    username = user_data.get("username")
                    local_id = user_data.get("id")
                    local_sync_status = str(user_data.get("sync_status") or "").lower()
                    local_is_deleted = bool(user_data.get("is_deleted", 0))

                    if local_is_deleted or local_sync_status == "deleted":
                        continue

                    existing_cloud = users_collection.find_one({"username": username})

                    if existing_cloud:
                        mongo_id = str(existing_cloud["_id"])
                        update_data = {
                            "full_name": user_data.get("full_name"),
                            "email": user_data.get("email"),
                            "role": user_data.get("role"),
                            "is_active": bool(user_data.get("is_active", 1)),
                            "last_modified": datetime.now(),
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                        if user_data.get("password_hash"):
                            update_data["password_hash"] = user_data["password_hash"]

                        update_result = users_collection.update_one(
                            {"_id": existing_cloud["_id"]}, {"$set": update_data}
                        )
                        if update_result and (
                            getattr(update_result, "matched_count", 0) > 0
                            or getattr(update_result, "modified_count", 0) > 0
                        ):
                            cursor.execute(
                                """
                                UPDATE users
                                SET _mongo_id=?, sync_status='synced', dirty_flag = 0, is_deleted = 0
                                WHERE id=?
                                """,
                                (mongo_id, local_id),
                            )
                            uploaded_count += 1
                    else:
                        new_user = {
                            "username": username,
                            "password_hash": user_data.get("password_hash"),
                            "full_name": user_data.get("full_name"),
                            "email": user_data.get("email"),
                            "role": user_data.get("role", "sales"),
                            "is_active": bool(user_data.get("is_active", 1)),
                            "created_at": datetime.now(),
                            "last_modified": datetime.now(),
                            "sync_status": "synced",
                            "is_deleted": False,
                        }
                        result = users_collection.insert_one(new_user)
                        mongo_id = str(result.inserted_id)
                        cursor.execute(
                            """
                            UPDATE users
                            SET _mongo_id=?, sync_status='synced', dirty_flag = 0, is_deleted = 0
                            WHERE id=?
                            """,
                            (mongo_id, local_id),
                        )
                        uploaded_count += 1

                if uploaded_count > 0:
                    conn.commit()
                    logger.info("📤 تم رفع %s مستخدم للسحابة", uploaded_count)

                # === 2. تنزيل المستخدمين من السحابة ===
                logger.info("📥 جاري تنزيل المستخدمين من السحابة...")
                cloud_users = list(users_collection.find())
                if not cloud_users:
                    return

                downloaded_count = 0
                for u in cloud_users:
                    mongo_id = str(u["_id"])
                    username = u.get("username")
                    remote_sync_status = str(u.get("sync_status") or "").lower()
                    remote_is_deleted = bool(u.get("is_deleted", False)) or (
                        remote_sync_status == "deleted"
                    )

                    for field in ["created_at", "last_modified", "last_login"]:
                        if field in u and hasattr(u[field], "isoformat"):
                            u[field] = u[field].isoformat()

                    cursor.execute(
                        "SELECT id, sync_status, is_deleted FROM users WHERE _mongo_id = ? OR username = ?",
                        (mongo_id, username),
                    )
                    exists = cursor.fetchone()

                    if remote_is_deleted:
                        if exists and str(exists[1] or "").lower() not in (
                            "modified_offline",
                            "new_offline",
                        ):
                            cursor.execute(
                                """
                                UPDATE users SET
                                    _mongo_id=?, sync_status='deleted', dirty_flag = 0,
                                    is_deleted = 1, last_modified=?
                                WHERE id=?
                            """,
                                (
                                    mongo_id,
                                    u.get("last_modified", datetime.now().isoformat()),
                                    exists[0],
                                ),
                            )
                            downloaded_count += 1
                        continue

                    if exists:
                        local_sync_status = str(exists[1] or "").lower()
                        local_is_deleted = bool(exists[2])
                        if local_sync_status not in ("modified_offline", "new_offline"):
                            if local_is_deleted or local_sync_status == "deleted":
                                continue
                            cursor.execute(
                                """
                                UPDATE users SET
                                    full_name=?, email=?, role=?, is_active=?,
                                    password_hash=?, _mongo_id=?, sync_status='synced',
                                    dirty_flag = 0, is_deleted = 0, last_modified=?
                                WHERE id=?
                            """,
                                (
                                    u.get("full_name"),
                                    u.get("email"),
                                    u.get("role"),
                                    u.get("is_active", 1),
                                    u.get("password_hash"),
                                    mongo_id,
                                    u.get("last_modified", datetime.now().isoformat()),
                                    exists[0],
                                ),
                            )
                            downloaded_count += 1
                    else:
                        cursor.execute(
                            """
                            INSERT INTO users (
                                _mongo_id, username, full_name, email, role,
                                password_hash, is_active, sync_status, dirty_flag,
                                is_deleted, created_at, last_modified
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', 0, 0, ?, ?)
                        """,
                            (
                                mongo_id,
                                username,
                                u.get("full_name"),
                                u.get("email"),
                                u.get("role"),
                                u.get("password_hash"),
                                u.get("is_active", 1),
                                u.get("created_at", datetime.now().isoformat()),
                                u.get("last_modified", datetime.now().isoformat()),
                            ),
                        )
                        downloaded_count += 1

                conn.commit()
                logger.info(
                    "✅ تم مزامنة المستخدمين (رفع: %s، تنزيل: %s)",
                    uploaded_count,
                    downloaded_count,
                )

            finally:
                cursor.close()

        except Exception as e:
            logger.error("❌ خطأ في مزامنة المستخدمين: %s", e)

    # ==========================================
    # دوال التنظيف وإزالة التكرارات
    # ==========================================

    def remove_duplicates(self, table_name: str | None = None) -> dict[str, int]:
        """
        إزالة التكرارات من الجداول
        يحتفظ بالسجل الأقدم (أقل id) ويحذف الباقي
        """
        tables = [table_name] if table_name else self.TABLES
        results = {}

        # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
        cursor = self.repo.get_cursor()
        conn = self.repo.sqlite_conn

        try:
            for table in tables:
                try:
                    unique_field = self.UNIQUE_FIELDS.get(table, "name")
                    table_ref = self._sqlite_table_ref(table)
                    table_columns = self._sqlite_table_columns(cursor, table)
                    unique_field_ref = self._sqlite_column_ref(unique_field, allowed=table_columns)

                    # البحث عن التكرارات
                    duplicates_sql = f"SELECT {unique_field_ref}, COUNT(*) as cnt, MIN(id) as keep_id FROM {table_ref} WHERE {unique_field_ref} IS NOT NULL GROUP BY {unique_field_ref} HAVING cnt > 1"  # nosec B608
                    cursor.execute(duplicates_sql)
                    duplicates = cursor.fetchall()

                    deleted = 0
                    for dup in duplicates:
                        unique_value = dup[0]
                        keep_id = dup[2]

                        # حذف التكرارات (الاحتفاظ بالأقدم)
                        delete_duplicates_sql = f"DELETE FROM {table_ref} WHERE {unique_field_ref} = ? AND id != ?"  # nosec B608
                        cursor.execute(delete_duplicates_sql, (unique_value, keep_id))
                        deleted += cursor.rowcount

                    conn.commit()
                    results[table] = deleted

                    if deleted > 0:
                        logger.info("🗑️ %s: حذف %s سجل مكرر", table, deleted)

                except Exception as e:
                    logger.error("❌ خطأ في إزالة تكرارات %s: %s", table, e)
                    results[table] = 0
        finally:
            cursor.close()

        return results

    def force_full_resync(self) -> dict[str, Any]:
        """
        إعادة مزامنة كاملة قسرية
        1. حذف كل البيانات المحلية
        2. إعادة تحميل من السحابة
        """
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        logger.warning("⚠️ بدء إعادة المزامنة الكاملة القسرية...")

        # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
        cursor = self.repo.get_cursor()
        conn = self.repo.sqlite_conn

        try:
            # حذف البيانات المحلية (ما عدا المستخدمين)
            for table in self.TABLES:
                try:
                    table_ref = self._sqlite_table_ref(table)
                    delete_table_sql = f"DELETE FROM {table_ref}"  # nosec B608
                    cursor.execute(delete_table_sql)
                    logger.info("🗑️ تم مسح %s", table)
                except Exception as e:
                    logger.error("❌ خطأ في مسح %s: %s", table, e)

            conn.commit()
        finally:
            cursor.close()

        # إعادة التحميل من السحابة
        return self.full_sync_from_cloud()

    def sync_now(self) -> dict[str, Any]:
        """
        Legacy-compatible manual sync API.
        Performs push then pull and returns a compact summary.
        """
        if self._shutdown:
            result = {"success": False, "reason": "shutdown", "pushed": 0, "pulled": 0, "errors": 0}
            self._update_sync_metrics(success=False, records_synced=0)
            return result

        if not self.is_online:
            result = {"success": False, "reason": "offline", "pushed": 0, "pulled": 0, "errors": 0}
            self._update_sync_metrics(success=False, records_synced=0)
            return result

        if self._is_syncing:
            result = {
                "success": False,
                "reason": "full_sync_in_progress",
                "pushed": 0,
                "pulled": 0,
                "errors": 0,
            }
            self._update_sync_metrics(success=False, records_synced=0)
            return result

        if not self._delta_cycle_lock.acquire(timeout=2.0):
            result = {
                "success": False,
                "reason": "delta_busy",
                "pushed": 0,
                "pulled": 0,
                "errors": 0,
            }
            self._update_sync_metrics(success=False, records_synced=0)
            return result

        try:
            push_result = self.push_local_changes()
            pull_result = self.pull_remote_changes()
        finally:
            self._delta_cycle_lock.release()

        pushed = int(push_result.get("pushed", 0))
        pulled = int(pull_result.get("pulled", 0))
        deleted = int(push_result.get("deleted", 0)) + int(pull_result.get("deleted", 0))
        errors = int(push_result.get("errors", 0)) + int(pull_result.get("errors", 0))
        success = bool(push_result.get("success")) and bool(pull_result.get("success"))

        result: dict[str, Any] = {
            "success": success,
            "pushed": pushed,
            "pulled": pulled,
            "deleted": deleted,
            "errors": errors,
        }
        if not success:
            result["reason"] = (
                pull_result.get("reason") or push_result.get("reason") or "sync_failed"
            )

        self._update_sync_metrics(success=success, records_synced=(pushed + pulled))
        return result

    def get_sync_metrics(self) -> dict[str, Any]:
        """Legacy-compatible metrics API for settings screens."""
        with self._sync_metrics_lock:
            return dict(self._sync_metrics)

    def get_sync_status(self) -> dict[str, Any]:
        """الحصول على حالة المزامنة"""
        # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
        cursor = self.repo.get_cursor()
        status = {"is_online": self.is_online, "is_syncing": self._is_syncing, "tables": {}}

        try:
            for table in self.TABLES:
                try:
                    table_ref = self._sqlite_table_ref(table)
                    total_count_sql = f"SELECT COUNT(*) FROM {table_ref}"  # nosec B608
                    cursor.execute(total_count_sql)
                    total = cursor.fetchone()[0]

                    pending_count_sql = f"SELECT COUNT(*) FROM {table_ref} WHERE sync_status != 'synced' OR sync_status IS NULL"  # nosec B608
                    cursor.execute(pending_count_sql)
                    pending = cursor.fetchone()[0]

                    status["tables"][table] = {
                        "total": total,
                        "pending": pending,
                        "synced": total - pending,
                    }
                except Exception:
                    status["tables"][table] = {"total": 0, "pending": 0, "synced": 0}
        finally:
            cursor.close()

        return status

    def remove_cloud_duplicates(self) -> dict[str, int]:
        """
        إزالة التكرارات من MongoDB
        يحتفظ بالسجل الأقدم (بناءً على created_at)
        """
        if not self.is_online:
            return {}

        results = {}
        logger.info("🧹 جاري تنظيف التكرارات من السحابة...")

        for table in self.TABLES:
            try:
                deleted = self._remove_cloud_table_duplicates(table)
                results[table] = deleted
                if deleted > 0:
                    logger.info("🗑️ %s: حذف %s سجل مكرر من السحابة", table, deleted)
            except Exception as e:
                logger.error("❌ خطأ في تنظيف %s من السحابة: %s", table, e)
                results[table] = 0

        return results

    def _remove_cloud_table_duplicates(self, table_name: str) -> int:
        """إزالة التكرارات من جدول واحد في MongoDB"""
        unique_field = self.UNIQUE_FIELDS.get(table_name, "name")
        collection = self.repo.mongo_db[table_name]

        # البحث عن التكرارات باستخدام aggregation
        pipeline = [
            {
                "$group": {
                    "_id": f"${unique_field}",
                    "count": {"$sum": 1},
                    "docs": {"$push": {"_id": "$_id", "created_at": "$created_at"}},
                }
            },
            {"$match": {"count": {"$gt": 1}}},
        ]

        duplicates = list(collection.aggregate(pipeline))
        deleted = 0

        for dup in duplicates:
            docs = dup["docs"]
            # ترتيب حسب created_at (الأقدم أولاً)
            docs.sort(key=lambda x: x.get("created_at") or datetime.min)

            # حذف كل السجلات ما عدا الأول
            for doc in docs[1:]:
                collection.delete_one({"_id": doc["_id"]})
                deleted += 1

        return deleted

    def full_cleanup_and_sync(self) -> dict[str, Any]:
        """
        تنظيف كامل ومزامنة:
        1. تنظيف التكرارات من MongoDB
        2. تنظيف التكرارات المحلية
        3. مزامنة كاملة
        """
        results = {"cloud_cleanup": {}, "local_cleanup": {}, "sync": {}}

        if self.is_online:
            # تنظيف السحابة
            logger.info("☁️ جاري تنظيف السحابة...")
            results["cloud_cleanup"] = self.remove_cloud_duplicates()

        # تنظيف المحلي
        logger.info("💾 جاري تنظيف القاعدة المحلية...")
        results["local_cleanup"] = self.remove_duplicates()

        # مزامنة
        if self.is_online:
            logger.info("🔄 جاري المزامنة...")
            results["sync"] = self.full_sync_from_cloud()

        return results

    # ==========================================
    # ⚡ Bidirectional Delta Sync - NEW
    # ==========================================

    def _get_watermark_file_path(self) -> Path | None:
        """Resolve a stable watermark file path next to the local SQLite DB."""
        try:
            db_path = None

            if hasattr(self.repo, "LOCAL_DB_FILE"):
                candidate = getattr(self.repo, "LOCAL_DB_FILE", None)
                if isinstance(candidate, str) and candidate:
                    db_path = candidate

            if not db_path and hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn:
                cursor = self.repo.sqlite_conn.cursor()
                try:
                    cursor.execute("PRAGMA database_list")
                    rows = cursor.fetchall()
                    for row in rows:
                        file_path = row[2] if len(row) > 2 else None
                        if file_path:
                            db_path = file_path
                            break
                finally:
                    cursor.close()

            if not db_path or db_path == ":memory:":
                return None

            return Path(db_path).resolve().parent / "sync_watermarks.json"
        except Exception as e:
            logger.debug("فشل تحديد مسار ملف watermark: %s", e)
            return None

    def _load_watermarks(self):
        """تحميل Watermarks من ملف محلي"""
        try:
            watermark_file = self._get_watermark_file_path()
            if watermark_file and watermark_file.exists():
                with open(watermark_file, encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    sanitized: dict[str, str] = {}
                    for table, value in loaded.items():
                        key = str(table or "").strip()
                        if not key:
                            continue
                        text = str(value or "").strip()
                        if not text:
                            continue
                        sanitized[key] = text
                    self._watermarks = sanitized
                else:
                    self._watermarks = {}
                logger.info("📍 تم تحميل Watermarks: %s جداول", len(self._watermarks))
                return
            self._watermarks = {}
        except Exception as e:
            logger.debug("فشل تحميل Watermarks: %s", e)
            self._watermarks = {}

    def _save_watermarks(self):
        """حفظ Watermarks إلى ملف محلي"""
        try:
            watermark_file = self._get_watermark_file_path()
            if not watermark_file:
                return
            with open(watermark_file, "w", encoding="utf-8") as f:
                json.dump(self._watermarks, f, ensure_ascii=False, indent=2)
            logger.debug("📍 تم حفظ Watermarks")
        except Exception as e:
            logger.debug("فشل حفظ Watermarks: %s", e)

    def push_local_changes(self, target_tables: set[str] | None = None) -> dict[str, Any]:
        """
        ⚡ Push all locally modified records to MongoDB
        Returns: dict with counts of pushed records and any errors
        """
        if self.repo is None:
            return {"success": False, "reason": "sqlite_closed"}
        if hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn is None:
            return {"success": False, "reason": "sqlite_closed"}
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        results = {"success": True, "pushed": 0, "deleted": 0, "errors": 0}
        changed_tables: set[str] = set()

        try:
            server_now_dt = self._get_mongo_server_now()
            server_now_iso = self._to_iso_timestamp(server_now_dt)
            cursor = self.repo.get_cursor()

            if target_tables:
                table_names = [t for t in self.TABLES if t in target_tables]
            else:
                table_names = list(self.TABLES)

            for table in table_names:
                try:
                    before_pushed = results["pushed"]
                    before_deleted = results["deleted"]
                    table_ref = self._sqlite_table_ref(table)
                    # التحقق من وجود الجدول
                    if not self._sqlite_table_exists(cursor, table):
                        continue

                    # جلب كل السجلات المحلية غير المتزامنة
                    # ملاحظة: بعض العمليات تضبط sync_status فقط بدون dirty_flag.
                    dirty_records_sql = f"SELECT * FROM {table_ref} WHERE dirty_flag = 1 OR sync_status IS NULL OR sync_status IN ('new_offline', 'modified_offline', 'pending', 'deleted') OR _mongo_id IS NULL LIMIT ?"  # nosec B608
                    cursor.execute(dirty_records_sql, (self._delta_push_batch_limit,))
                    dirty_records = cursor.fetchall()

                    if not dirty_records:
                        continue

                    columns = [desc[0] for desc in cursor.description]
                    table_columns = set(columns)
                    collection = self.repo.mongo_db[table]

                    for row in dirty_records:
                        try:
                            record = dict(zip(columns, row, strict=False))
                            local_id = record.get("id")
                            mongo_id = record.get("_mongo_id")
                            sync_status = str(record.get("sync_status") or "").lower()
                            is_deleted = bool(record.get("is_deleted", 0))
                            unique_field = self.UNIQUE_FIELDS.get(table, "name")
                            unique_value = record.get(unique_field)

                            if is_deleted or sync_status == "deleted":
                                # حذف منطقي في السحابة لضمان مزامنة الحذف عبر Delta Sync
                                now_dt = server_now_dt
                                remote_error = False
                                remote_matched = False

                                if mongo_id:
                                    try:
                                        try:
                                            from bson import ObjectId

                                            result = collection.update_one(
                                                {"_id": ObjectId(mongo_id)},
                                                {
                                                    "$set": {
                                                        "is_deleted": True,
                                                        "sync_status": "deleted",
                                                        "last_modified": now_dt,
                                                    }
                                                },
                                            )
                                        except Exception:
                                            result = collection.update_one(
                                                {"_id": mongo_id},
                                                {
                                                    "$set": {
                                                        "is_deleted": True,
                                                        "sync_status": "deleted",
                                                        "last_modified": now_dt,
                                                    }
                                                },
                                            )
                                        remote_matched = bool(
                                            getattr(result, "matched_count", 0)
                                            or getattr(result, "modified_count", 0)
                                        )
                                    except Exception as del_err:
                                        remote_error = True
                                        logger.debug("تعذر تعليم الحذف في MongoDB: %s", del_err)

                                if not remote_matched and unique_value:
                                    try:
                                        result = collection.update_one(
                                            {unique_field: unique_value},
                                            {
                                                "$set": {
                                                    "is_deleted": True,
                                                    "sync_status": "deleted",
                                                    "last_modified": now_dt,
                                                }
                                            },
                                        )
                                        remote_matched = bool(
                                            getattr(result, "matched_count", 0)
                                            or getattr(result, "modified_count", 0)
                                        )
                                    except Exception as del_err:
                                        remote_error = True
                                        logger.debug(
                                            "تعذر تعليم الحذف بالـ unique field: %s", del_err
                                        )

                                if remote_error:
                                    results["errors"] += 1
                                    continue

                                # حذف محلياً بعد نجاح التعليم أو عدم وجود سجل في السحابة
                                delete_local_sql = (
                                    f"DELETE FROM {table_ref} WHERE id = ?"  # nosec B608
                                )
                                cursor.execute(delete_local_sql, (local_id,))
                                results["deleted"] += 1
                            else:
                                record = self._normalize_project_links_for_push(
                                    cursor,
                                    table,
                                    record,
                                    table_columns,
                                    server_now_iso,
                                )
                                record = self._normalize_client_links_for_push(
                                    cursor,
                                    table,
                                    record,
                                    table_columns,
                                    server_now_iso,
                                )
                                # Upsert إلى MongoDB
                                clean_record = {
                                    k: v
                                    for k, v in record.items()
                                    if k not in ["id", "sync_status", "dirty_flag", "is_deleted"]
                                }
                                clean_record["last_modified"] = server_now_iso
                                if table == "notifications" and not clean_record.get("device_id"):
                                    clean_record["device_id"] = self._device_id

                                if mongo_id:
                                    try:
                                        from bson import ObjectId

                                        collection.update_one(
                                            {"_id": ObjectId(mongo_id)},
                                            {"$set": clean_record},
                                            upsert=True,
                                        )
                                    except Exception:
                                        collection.update_one(
                                            {"_id": mongo_id},
                                            {"$set": clean_record},
                                            upsert=True,
                                        )
                                else:
                                    result = collection.insert_one(clean_record)
                                    mongo_id = str(result.inserted_id)
                                    set_mongo_id_sql = f"UPDATE {table_ref} SET _mongo_id = ? WHERE id = ?"  # nosec B608
                                    cursor.execute(set_mongo_id_sql, (mongo_id, local_id))

                                # تحديث dirty_flag و sync_status
                                if "last_modified" in columns:
                                    mark_synced_sql = f"UPDATE {table_ref} SET dirty_flag = 0, sync_status = 'synced', last_modified = ? WHERE id = ?"  # nosec B608
                                    cursor.execute(mark_synced_sql, (server_now_iso, local_id))
                                else:
                                    mark_synced_sql = f"UPDATE {table_ref} SET dirty_flag = 0, sync_status = 'synced' WHERE id = ?"  # nosec B608
                                    cursor.execute(mark_synced_sql, (local_id,))
                                results["pushed"] += 1

                        except Exception as e:
                            logger.debug("خطأ في رفع سجل من %s: %s", table, e)
                            results["errors"] += 1

                    self.repo.sqlite_conn.commit()

                except Exception as e:
                    logger.debug("خطأ في رفع جدول %s: %s", table, e)
                finally:
                    if results["pushed"] > before_pushed or results["deleted"] > before_deleted:
                        changed_tables.add(table)

            cursor.close()

            if results["pushed"] > 0 or results["deleted"] > 0:
                logger.info("⬆️ Delta رفع: %s، حذف: %s", results["pushed"], results["deleted"])
                self._emit_sync_pings(changed_tables)

        except Exception as e:
            if self._shutdown and self._is_closed_sqlite_error(e):
                logger.debug("تجاهل push بعد الإغلاق: %s", e)
                return {"success": False, "reason": "shutdown"}
            logger.error("❌ خطأ في push_local_changes: %s", e)
            results["success"] = False
            results["error"] = str(e)

        return results

    def pull_remote_changes(self) -> dict[str, Any]:
        """
        ⚡ Pull changes from MongoDB since last sync (watermark-based delta sync)
        Only pulls records where last_modified > watermark
        Returns: dict with counts of pulled/deleted records
        """
        if self.repo is None:
            return {"success": False, "reason": "sqlite_closed"}
        if hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn is None:
            return {"success": False, "reason": "sqlite_closed"}
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        if self._is_syncing:
            return {"success": False, "reason": "already_syncing"}

        results = {"success": True, "pulled": 0, "deleted": 0, "errors": 0}
        changed_tables: set[str] = set()
        watermarks_dirty = False

        try:
            reference_now = self._get_mongo_server_now()
            cursor = self.repo.get_cursor()

            for table in self.TABLES:
                try:
                    before_pulled = results["pulled"]
                    before_deleted = results["deleted"]

                    # الحصول على Watermark لهذا الجدول
                    watermark = str(self._watermarks.get(table) or "1970-01-01T00:00:00").strip()
                    if watermark and self._parse_iso_datetime(watermark) is None:
                        watermark = "1970-01-01T00:00:00"
                        self._watermarks[table] = watermark
                        watermarks_dirty = True
                    watermark_dt = self._normalize_datetime(self._parse_iso_datetime(watermark))
                    if watermark_dt and watermark_dt > reference_now + timedelta(seconds=30):
                        fallback_dt = reference_now - timedelta(minutes=5)
                        watermark = fallback_dt.isoformat()
                        self._watermarks[table] = watermark
                        watermarks_dirty = True

                    # جلب السجلات من MongoDB المحدّثة بعد الـ watermark
                    collection = self.repo.mongo_db[table]
                    query = self._build_last_modified_query(
                        watermark, upper_bound_dt=reference_now + timedelta(seconds=2)
                    )
                    if table == "notifications":
                        query = self._merge_query_with_notification_filter(query)
                    projection = None
                    if table == "clients" and self._lazy_logo_enabled:
                        projection = {"logo_data": 0}
                    if projection is None:
                        remote_records = list(collection.find(query))
                    else:
                        try:
                            remote_records = list(collection.find(query, projection))
                        except TypeError:
                            # توافق مع Fakes قديمة في الاختبارات
                            remote_records = list(collection.find(query))

                    if not remote_records:
                        continue

                    # التحقق من وجود الجدول محلياً
                    if not self._sqlite_table_exists(cursor, table):
                        continue

                    # الحصول على أعمدة الجدول
                    table_columns = self._sqlite_table_columns(cursor, table)
                    table_ref = self._sqlite_table_ref(table)

                    logo_clients = 0

                    for remote in remote_records:
                        try:
                            mongo_id = str(remote["_id"])
                            is_deleted = remote.get("is_deleted", False)
                            last_modified_iso = self._to_iso_timestamp(
                                remote.get("last_modified", "")
                            )

                            # البحث عن السجل المحلي
                            local_lookup_sql = f"SELECT id, last_modified, sync_status, is_deleted FROM {table_ref} WHERE _mongo_id = ?"  # nosec B608
                            cursor.execute(local_lookup_sql, (mongo_id,))
                            local_row = cursor.fetchone()
                            local_id = local_row[0] if local_row else None
                            local_last_modified = (
                                self._to_iso_timestamp(local_row[1]) if local_row else ""
                            )
                            local_sync_status = str(local_row[2] or "").lower() if local_row else ""
                            local_is_deleted = bool(local_row[3]) if local_row else False

                            if is_deleted:
                                # حذف من MongoDB -> حذف محلياً
                                if local_id:
                                    delete_local_sql = (
                                        f"DELETE FROM {table_ref} WHERE id = ?"  # nosec B608
                                    )
                                    cursor.execute(delete_local_sql, (local_id,))
                                    results["deleted"] += 1
                            else:
                                # لا نعيد إحياء صف محلي محذوف قبل أن تُدفَع حذفه إلى السحابة.
                                if local_id and (
                                    local_is_deleted or local_sync_status == "deleted"
                                ):
                                    continue

                                # تحضير البيانات
                                item_data = self._prepare_cloud_data(remote, table_name=table)
                                if item_data.pop("__skip_sync__", False):
                                    logger.warning(
                                        "⚠️ تم تجاهل سجل projects غير صالح أثناء delta pull (mongo_id=%s)",
                                        mongo_id,
                                    )
                                    continue
                                item_data["_mongo_id"] = mongo_id
                                item_data["sync_status"] = "synced"
                                item_data["dirty_flag"] = 0
                                item_data["is_deleted"] = 0
                                if table == "clients" and bool(item_data.get("has_logo", 0)):
                                    logo_clients += 1

                                # تصفية الحقول
                                filtered = {
                                    k: v for k, v in item_data.items() if k in table_columns
                                }

                                # Extra safety: when query returns broad sets, skip no-op rows.
                                if (
                                    local_id
                                    and last_modified_iso
                                    and local_last_modified
                                    and not self._is_newer_timestamp(
                                        last_modified_iso, local_last_modified
                                    )
                                ):
                                    continue

                                if local_id:
                                    # تحديث السجل الموجود
                                    set_clause = self._sqlite_set_clause_sql(
                                        list(filtered.keys()), table_columns=table_columns
                                    )
                                    values = list(filtered.values()) + [local_id]
                                    update_local_sql = f"UPDATE {table_ref} SET {set_clause} WHERE id = ?"  # nosec B608
                                    cursor.execute(update_local_sql, values)
                                else:
                                    # إدراج سجل جديد
                                    cols = self._sqlite_column_list_sql(
                                        list(filtered.keys()), table_columns=table_columns
                                    )
                                    placeholders = ", ".join(["?" for _ in filtered])
                                    insert_local_sql = f"INSERT INTO {table_ref} ({cols}) VALUES ({placeholders})"  # nosec B608
                                    cursor.execute(insert_local_sql, list(filtered.values()))
                                results["pulled"] += 1

                        except Exception as e:
                            logger.debug("خطأ في سحب سجل من %s: %s", table, e)
                            results["errors"] += 1

                    if remote_records:
                        # ⚡ CRITICAL: Update watermark based on the LATEST record found
                        try:
                            latest_ts = ""
                            for remote_row in remote_records:
                                row_ts = self._to_iso_timestamp(remote_row.get("last_modified", ""))
                                if self._is_newer_timestamp(row_ts, latest_ts):
                                    latest_ts = row_ts
                            current_watermark = self._watermarks.get(table, "")

                            if self._is_newer_timestamp(latest_ts, current_watermark):
                                self._watermarks[table] = latest_ts
                                watermarks_dirty = True
                                logger.debug("📍 Watermark updated for %s: %s", table, latest_ts)
                        except Exception as wm_err:
                            logger.error("❌ Failed to update watermark for %s: %s", table, wm_err)

                    table_changed = (
                        results["pulled"] > before_pulled or results["deleted"] > before_deleted
                    )
                    if table_changed:
                        self.repo.sqlite_conn.commit()
                    if table == "clients" and logo_clients > 0 and self._lazy_logo_enabled:
                        logger.info(
                            "📷 clients delta: %s عميل لديه شعار (metadata only - lazy mode)",
                            logo_clients,
                        )
                    if table_changed:
                        self._invalidate_repository_cache(table)
                        changed_tables.add(table)

                except Exception as e:
                    logger.debug("خطأ في سحب جدول %s: %s", table, e)

            cursor.close()

            # حفظ الـ watermarks (مرة واحدة في نهاية الدورة لتقليل I/O)
            if watermarks_dirty:
                self._save_watermarks()

            if results["pulled"] > 0 or results["deleted"] > 0:
                logger.info("⬇️ Delta سحب: %s، حذف: %s", results["pulled"], results["deleted"])
                if changed_tables:
                    try:
                        from core.signals import app_signals

                        for table_name in sorted(changed_tables):
                            app_signals.emit_ui_data_changed(table_name)
                    except Exception as signal_err:
                        logger.debug("تعذر بث إشارات UI بعد delta pull: %s", signal_err)
                # إرسال إشارة لتحديث الواجهة
                try:
                    self.data_synced.emit()
                except RuntimeError:
                    pass  # Qt object deleted

        except Exception as e:
            if self._shutdown and self._is_closed_sqlite_error(e):
                logger.debug("تجاهل pull بعد الإغلاق: %s", e)
                return {"success": False, "reason": "shutdown"}
            logger.error("❌ خطأ في pull_remote_changes: %s", e)
            results["success"] = False
            results["error"] = str(e)

        return results

    def _run_delta_cycle(self) -> dict[str, Any]:
        """Run one guarded push+pull cycle without overlapping with another delta cycle."""
        if self.repo is None:
            return {"success": False, "reason": "sqlite_closed"}
        if hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn is None:
            return {"success": False, "reason": "sqlite_closed"}
        if self._shutdown:
            return {"success": False, "reason": "shutdown"}
        if self._is_syncing:
            return {"success": False, "reason": "full_sync_in_progress"}

        if not self._delta_cycle_lock.acquire(blocking=False):
            return {"success": False, "reason": "delta_busy"}

        try:
            push_result = self.push_local_changes()
            pull_result = self.pull_remote_changes()
            return {
                "success": bool(push_result.get("success")) and bool(pull_result.get("success")),
                "pushed": int(push_result.get("pushed", 0)),
                "pulled": int(pull_result.get("pulled", 0)),
                "deleted": int(push_result.get("deleted", 0)) + int(pull_result.get("deleted", 0)),
                "errors": int(push_result.get("errors", 0)) + int(pull_result.get("errors", 0)),
            }
        finally:
            self._delta_cycle_lock.release()

    def _run_table_reconcile_cycle(self, table: str) -> dict[str, Any]:
        """
        Run one guarded targeted cycle for a single table.
        Used by remote notification-triggered pulls to bypass watermark stalls safely.
        """
        if table not in self.TABLES:
            return {"success": False, "reason": "invalid_table"}
        if self.repo is None:
            return {"success": False, "reason": "sqlite_closed"}
        if hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn is None:
            return {"success": False, "reason": "sqlite_closed"}
        if self._shutdown:
            return {"success": False, "reason": "shutdown"}
        if self._is_syncing:
            return {"success": False, "reason": "full_sync_in_progress"}

        if not self._delta_cycle_lock.acquire(blocking=False):
            return {"success": False, "reason": "delta_busy"}

        pushed = 0
        errors = 0
        try:
            push_result = self.push_local_changes({table})
            pushed = int(push_result.get("pushed", 0))
            errors += int(push_result.get("errors", 0))
            self._sync_single_table_from_cloud(table)
            try:
                from core.signals import app_signals

                app_signals.emit_ui_data_changed(table)
            except Exception:
                pass
            try:
                self.data_synced.emit()
            except RuntimeError:
                pass
            return {
                "success": bool(push_result.get("success", True)),
                "pushed": pushed,
                "pulled": 0,
                "deleted": int(push_result.get("deleted", 0)),
                "errors": errors,
                "table": table,
            }
        except Exception as e:
            logger.debug("خطأ في table reconcile cycle (%s): %s", table, e)
            return {
                "success": False,
                "reason": "table_reconcile_failed",
                "table": table,
                "error": str(e),
            }
        finally:
            self._delta_cycle_lock.release()

    def force_pull(self, table: str = None):
        """
        ⚡ Force immediate pull (for screen open events)
        Pushes local changes first, then pulls remote changes
        """
        if self._shutdown or self._is_syncing or not self.is_online:
            return

        def pull_thread():
            if self._shutdown:
                return
            try:
                target_table = table if isinstance(table, str) and table in self.TABLES else None
                if target_table:
                    self._run_table_reconcile_cycle(target_table)
                else:
                    # Fallback: full delta cycle for broad refresh.
                    self._run_delta_cycle()
            except Exception as e:
                logger.debug("خطأ في force_pull: %s", e)

        threading.Thread(target=pull_thread, daemon=True).start()

    def start_delta_sync(self, interval_seconds: int = DEFAULT_DELTA_SYNC_INTERVAL_SECONDS):
        """
        ⚡ بدء نظام المزامنة التفاضلية (Delta Sync)
        يقوم بسحب التغييرات الجديدة كل فترة محددة
        """
        if self._delta_pull_timer:
            try:
                self._delta_pull_timer.stop()
            except Exception:
                pass
            self._delta_pull_timer = None

        if self._delta_thread and self._delta_thread.is_alive():
            try:
                self._delta_thread_stop.set()
                self._delta_thread.join(timeout=0.5)
            except Exception:
                pass
        self._delta_thread_stop = threading.Event()

        interval_seconds = self._safe_int(
            interval_seconds, DEFAULT_DELTA_SYNC_INTERVAL_SECONDS, 1, 300
        )
        self._delta_sync_interval_seconds = interval_seconds
        interval_seconds = max(1, int(interval_seconds))

        def delta_loop():
            idle_streak = 0
            while not self._shutdown and not self._delta_thread_stop.is_set():
                backoff_factor = 1
                if self._realtime_enabled and idle_streak >= 2:
                    backoff_factor = min(4, 1 + (idle_streak // 2))
                wait_seconds = float(interval_seconds * backoff_factor)
                if self._delta_thread_stop.wait(wait_seconds):
                    break
                if self._shutdown or self._delta_thread_stop.is_set():
                    break
                if self._is_syncing or not self.is_online:
                    continue
                try:
                    result = self._run_delta_cycle()
                    self._last_delta_cycle_mono = time.monotonic()
                    changed = (
                        int(result.get("pushed", 0))
                        + int(result.get("pulled", 0))
                        + int(result.get("deleted", 0))
                    )
                    if changed > 0:
                        self._last_delta_change_mono = self._last_delta_cycle_mono
                        idle_streak = 0
                    elif result.get("reason") in {"delta_busy", "full_sync_in_progress"}:
                        idle_streak = max(0, idle_streak - 1)
                    else:
                        idle_streak = min(10, idle_streak + 1)
                except Exception as e:
                    logger.debug("خطأ في periodic delta sync: %s", e)

        self._delta_thread = threading.Thread(
            target=delta_loop,
            daemon=True,
            name="unified-delta-sync",
        )
        self._last_delta_cycle_mono = time.monotonic()
        self._delta_thread.start()

        logger.info("⏰ بدء Delta Sync كل %s ثانية (Adaptive idle backoff مفعّل)", interval_seconds)


def create_unified_sync_manager(repository) -> UnifiedSyncManagerV3:
    """إنشاء مدير مزامنة موحد"""
    return UnifiedSyncManagerV3(repository)
