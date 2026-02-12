# الملف: core/unified_sync.py
"""
🔄 نظام المزامنة الموحد - MongoDB First
MongoDB هو المصدر الرئيسي، SQLite نسخة محلية للـ offline فقط

المبدأ:
- عند الاتصال: MongoDB = الحقيقة المطلقة
- عند عدم الاتصال: SQLite يحفظ التغييرات مؤقتاً
- عند استعادة الاتصال: رفع التغييرات المحلية ثم مسح وإعادة تحميل من MongoDB
"""

import hashlib
import json
import os
import platform
import threading
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from core.logger import get_logger

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


def _get_stable_device_id() -> str:
    """Return a stable device id used for cross-device sync pings."""
    try:
        machine_info = f"{platform.node()}-{platform.machine()}-{platform.processor()}"
        try:
            digest = hashlib.md5(machine_info.encode(), usedforsecurity=False).hexdigest()
        except TypeError:
            digest = hashlib.sha256(machine_info.encode()).hexdigest()
        return digest[:8]
    except Exception:
        device_file = os.path.join(os.path.expanduser("~"), ".skywave_device_id")
        if os.path.exists(device_file):
            try:
                with open(device_file, encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        new_id = str(uuid.uuid4())[:8]
        try:
            with open(device_file, "w", encoding="utf-8") as f:
                f.write(new_id)
        except OSError:
            pass
        return new_id


# ==================== ثوابت التوقيت (بالمللي ثانية) ====================
FULL_SYNC_INTERVAL_MS = 15 * 60 * 1000
QUICK_SYNC_INTERVAL_MS = 3 * 60 * 1000
CONNECTION_CHECK_INTERVAL_MS = 90 * 1000
CLOUD_PULL_INTERVAL_MS = 45 * 1000
DEFAULT_DELTA_SYNC_INTERVAL_SECONDS = 2
DEFAULT_REALTIME_CHANGE_STREAM_MAX_AWAIT_MS = 250
DEFAULT_LAZY_LOGO_ENABLED = True
DEFAULT_LOGO_FETCH_BATCH_LIMIT = 10


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
        self._is_syncing = False
        self._max_retries = 3
        self._last_online_status = None
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
        self._realtime_pull_dedupe_ms = 400
        self._last_realtime_pull_ms: dict[str, int] = {}
        self._queued_realtime_tables: set[str] = set()
        self._instant_sync_schedule_lock = threading.Lock()
        self._instant_sync_pending_tables: set[str] = set()
        self._instant_sync_worker_running = False
        self._instant_sync_dedupe_ms = 250
        self._last_instant_sync_request_ms: dict[str, int] = {}
        self._device_id = _get_stable_device_id()
        self._last_sync_ping_at: dict[str, float] = {}

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

        logger.info("✅ تم تهيئة UnifiedSyncManager - مزامنة محسّنة للأداء")

    def _emit_sync_pings(self, tables: set[str]) -> None:
        if not tables:
            return
        if not self.is_online or self.repo is None or self.repo.mongo_db is None:
            return
        collection = self.repo.mongo_db["notifications"]
        now_iso = datetime.now().isoformat()
        now_ts = time.time()
        for table in tables:
            # Avoid notification table echo storms.
            if table == "notifications":
                continue
            last_ping = self._last_sync_ping_at.get(table, 0.0)
            if (now_ts - last_ping) < 0.6:
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
        if hasattr(value, "isoformat"):
            try:
                return value.isoformat()
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

    def _build_last_modified_query(self, watermark: str) -> dict[str, Any]:
        """Build query that handles mixed datetime/string storage in MongoDB."""
        conditions: list[dict[str, Any]] = [{"last_modified": {"$gt": watermark}}]
        watermark_dt = self._parse_iso_datetime(watermark)
        if watermark_dt is not None:
            conditions.append({"last_modified": {"$gt": watermark_dt}})
        return conditions[0] if len(conditions) == 1 else {"$or": conditions}

    @staticmethod
    def _format_bytes(value: int) -> str:
        size = float(max(0, int(value)))
        units = ["B", "KB", "MB", "GB"]
        unit_idx = 0
        while size >= 1024 and unit_idx < (len(units) - 1):
            size /= 1024.0
            unit_idx += 1
        return f"{size:.1f}{units[unit_idx]}"

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

                result = self._run_delta_cycle()
                if result.get("reason") in {"delta_busy", "full_sync_in_progress"}:
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
            # ⚡ استخدام cursor منفصل لتجنب Recursive cursor error
            cursor = self.repo.get_cursor()
            try:
                # ⚡ التحقق من وجود الجدول أولاً
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                )
                if not cursor.fetchone():
                    return  # الجدول غير موجود

                cursor.execute(
                    f"SELECT * FROM {table} WHERE sync_status != 'synced' OR sync_status IS NULL"
                )
                rows = cursor.fetchall()

                if not rows:
                    return

                columns = [desc[0] for desc in cursor.description]
                collection = self.repo.mongo_db[table]

                updated_any = False
                for row in rows:
                    record = dict(zip(columns, row, strict=False))
                    mongo_id = record.get("_mongo_id")

                    # تنظيف البيانات
                    clean_record = {
                        k: v
                        for k, v in record.items()
                        if k not in ["id", "sync_status", "last_synced"]
                    }

                    if mongo_id:
                        # تحديث
                        from bson import ObjectId

                        collection.update_one(
                            {"_id": ObjectId(mongo_id)}, {"$set": clean_record}, upsert=True
                        )
                    else:
                        # إضافة جديد
                        result = collection.insert_one(clean_record)
                        # تحديث الـ mongo_id محلياً
                        cursor.execute(
                            f"UPDATE {table} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                            (str(result.inserted_id), record.get("id")),
                        )
                        updated_any = True

                    # تحديث حالة المزامنة
                    cursor.execute(
                        f"UPDATE {table} SET sync_status = 'synced' WHERE id = ?",
                        (record.get("id"),),
                    )
                    updated_any = True
                if updated_any:
                    self.repo.sqlite_conn.commit()
            finally:
                cursor.close()

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

    def _check_connection(self):
        """🔌 فحص حالة الاتصال - محسّن"""
        if self._shutdown:  # ⚡ تجاهل إذا تم الإغلاق
            return

        try:
            # ⚡ فحص أن MongoDB client لا يزال متاحاً قبل الاستخدام
            if self.repo is None or self.repo.mongo_client is None or self.repo.mongo_db is None:
                current_status = False
            else:
                try:
                    # محاولة ping للتأكد من أن الاتصال فعال
                    self.repo.mongo_client.admin.command("ping")
                    current_status = True
                except Exception:
                    current_status = False

            # إرسال إشارة عند تغيير الحالة فقط
            if current_status != self._last_online_status:
                previous_status = self._last_online_status
                self._last_online_status = current_status
                try:
                    if not self._shutdown:
                        self.connection_changed.emit(current_status)
                except RuntimeError:
                    return  # Qt object deleted

                if current_status:
                    logger.info("🟢 تم استعادة الاتصال")
                    # لا نطلق Full Sync فوري في أول تشغيل (None -> True)
                    # لأن _initial_sync مجدول بالفعل بعد بدء النظام.
                    if previous_status is False:
                        QTimer.singleShot(300, self._run_full_sync_async)
                else:
                    logger.warning("🔴 انقطع الاتصال - العمل في وضع Offline")
        except Exception:
            # تجاهل الأخطاء
            pass

    def _initial_sync(self):
        """🚀 المزامنة الأولية عند بدء التشغيل - تفاضلية للسرعة"""
        if self._shutdown:
            return

        if not self.is_online:
            logger.info("📴 لا يوجد اتصال - العمل بالبيانات المحلية")
            return

        logger.info("🚀 بدء المزامنة الأولية...")

        def sync_thread():
            if self._shutdown:
                return
            try:
                result = self.full_sync_from_cloud()
                if result.get("success"):
                    logger.info("✅ المزامنة الأولية: تم توحيد البيانات بالكامل")
                else:
                    logger.warning("⚠️ المزامنة الأولية لم تكتمل: %s", result.get("reason"))
            except Exception as e:
                logger.warning("⚠️ المزامنة الأولية: %s", e)

        # استخدام QTimer بدلاً من daemon thread
        threading.Thread(target=sync_thread, daemon=True).start()

    def _auto_full_sync(self):
        """🔄 المزامنة التلقائية - تفاضلية للسرعة"""
        if self._shutdown or self._is_syncing or not self.is_online:
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
                        cursor.execute(
                            f"""
                            SELECT COUNT(*) FROM {table}
                            WHERE sync_status != 'synced' OR sync_status IS NULL
                        """
                        )
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
        """التحقق من الاتصال مع فحص حالة MongoDB client"""
        if self.repo is None:
            return False

        # ⚡ فحص أن MongoDB client متاح ولم يُغلق
        if self.repo.mongo_client is None or self.repo.mongo_db is None:
            return False

        try:
            # محاولة ping سريعة للتأكد من أن الاتصال فعال
            self.repo.mongo_client.admin.command("ping")
            return True
        except Exception:
            return False

    def _wait_for_connection(self, timeout: int = 10) -> bool:
        """⚡ انتظار اتصال MongoDB مع timeout"""
        import time

        waited = 0
        while not self.is_online and waited < timeout:
            time.sleep(0.5)
            waited += 0.5
        return self.is_online

    def _run_full_sync_async(self):
        if self._shutdown or self._is_syncing or not self.is_online:
            return

        def worker():
            if self._shutdown:
                return
            try:
                self.full_sync_from_cloud()
            except Exception as e:
                logger.debug("خطأ في المزامنة الخلفية: %s", e)

        threading.Thread(target=worker, daemon=True).start()

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
                    except Exception as e:
                        logger.error("❌ خطأ في مزامنة %s: %s", table, e)
                        results["tables"][table] = {"error": str(e)}

            logger.info("✅ اكتملت المزامنة: %s سجل", results["total_synced"])
            self._update_sync_metrics(success=True, records_synced=results["total_synced"])
            self.sync_completed.emit(results)

            # ⚡ إعادة حساب أرصدة الحسابات النقدية بعد المزامنة
            try:
                from services.accounting_service import AccountingService

                # إبطال الـ cache أولاً
                AccountingService._hierarchy_cache = None
                AccountingService._hierarchy_cache_time = 0
                logger.info("📊 تم إبطال cache الحسابات - سيتم إعادة الحساب عند فتح تاب المحاسبة")
            except Exception as e:
                logger.warning("⚠️ فشل إبطال cache الحسابات: %s", e)

            # ⚡ إرسال إشارات تحديث البيانات لتحديث الواجهة
            try:
                from core.signals import app_signals

                app_signals.emit_data_changed("clients")
                app_signals.emit_data_changed("projects")
                app_signals.emit_data_changed("accounts")
                app_signals.emit_data_changed("payments")
                app_signals.emit_data_changed("expenses")
                logger.info("📢 تم إرسال إشارات تحديث الواجهة")
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
                cloud_data = list(self.repo.mongo_db[table_name].find())
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
                cursor.execute(f"PRAGMA table_info({table_name})")
                table_columns = {row[1] for row in cursor.fetchall()}

                # جمع كل الـ mongo_ids من السحابة
                cloud_mongo_ids = set()
                logo_clients = 0
                logo_payload_bytes = 0

                for i, cloud_item in enumerate(cloud_data):
                    self.sync_progress.emit(table_name, i + 1, len(cloud_data))

                    mongo_id = str(cloud_item["_id"])
                    cloud_mongo_ids.add(mongo_id)
                    unique_value = cloud_item.get(unique_field)

                    # تحضير البيانات
                    item_data = self._prepare_cloud_data(cloud_item, table_name=table_name)
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
                        # تحديث السجل الموجود
                        self._update_record(cursor, table_name, local_id, filtered)
                        stats["updated"] += 1
                    else:
                        # إدراج سجل جديد
                        self._insert_record(cursor, table_name, filtered)
                        stats["inserted"] += 1

                    stats["synced"] += 1

                # حذف السجلات المحلية غير الموجودة في السحابة
                deleted = self._delete_orphan_records(cursor, table_name, cloud_mongo_ids)
                stats["deleted"] = deleted

                conn.commit()
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
            # 1. البحث بـ _mongo_id أولاً
            cursor.execute(f"SELECT id FROM {table_name} WHERE _mongo_id = ?", (mongo_id,))
            row = cursor.fetchone()
            if row:
                return row[0]

            # 2. البحث بالحقل الفريد - وتحديث الـ mongo_id
            if unique_value and unique_field in table_columns:
                cursor.execute(
                    f"SELECT id, _mongo_id FROM {table_name} WHERE {unique_field} = ?",
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
                        cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (local_id,))

                        # Return None to signal that a new record should be inserted
                        return None

                    # ⚡ إصلاح: تحديث الـ mongo_id إذا كان مختلف (للجداول الأخرى)
                    if existing_mongo_id != mongo_id:
                        cursor.execute(
                            f"UPDATE {table_name} SET _mongo_id = ? WHERE id = ?",
                            (mongo_id, local_id),
                        )
                    return local_id
        except Exception as e:
            logger.debug("خطأ في البحث عن السجل: %s", e)

        return None

    def _delete_orphan_records(self, cursor, table_name: str, valid_mongo_ids: set) -> int:
        """
        حذف السجلات المحلية غير الموجودة في السحابة
        (السجلات التي لها _mongo_id لكنه غير موجود في السحابة)
        """
        if not valid_mongo_ids:
            return 0

        # جلب السجلات المحلية التي لها _mongo_id
        cursor.execute(f"SELECT id, _mongo_id FROM {table_name} WHERE _mongo_id IS NOT NULL")
        local_records = cursor.fetchall()

        deleted = 0
        for row in local_records:
            local_id = row[0]
            local_mongo_id = row[1]

            if local_mongo_id and local_mongo_id not in valid_mongo_ids:
                cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (local_id,))
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

        # تحويل التواريخ
        date_fields = [
            "created_at",
            "last_modified",
            "date",
            "issue_date",
            "due_date",
            "expiry_date",
            "start_date",
            "end_date",
            "last_attempt",
            "expires_at",
            "last_login",
        ]
        for field in date_fields:
            if field in item and hasattr(item[field], "isoformat"):
                item[field] = item[field].isoformat()

        # تحويل القوائم والكائنات إلى JSON
        json_fields = ["items", "lines", "data", "milestones"]
        for field in json_fields:
            if field in item and isinstance(item[field], list | dict):
                item[field] = json.dumps(item[field], ensure_ascii=False)

        # التأكد من الحقول المطلوبة
        now = datetime.now().isoformat()
        if not item.get("created_at"):
            item["created_at"] = now
        if not item.get("last_modified"):
            item["last_modified"] = now

        return item

    def _update_record(self, cursor, table_name: str, local_id: int, data: dict):
        """تحديث سجل محلي"""
        if not data:
            return

        set_clause = ", ".join([f"{k}=?" for k in data.keys()])
        values = list(data.values()) + [local_id]
        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE id=?", values)

    def _insert_record(self, cursor, table_name: str, data: dict):
        """إدراج سجل جديد مع التعامل مع التكرارات"""
        if not data:
            return

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

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])

        try:
            cursor.execute(
                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})", list(data.values())
            )
        except Exception as e:
            # في حالة UNIQUE constraint - نحاول التحديث بدلاً من الإدراج
            if "UNIQUE constraint" in str(e):
                # البحث عن السجل الموجود وتحديثه
                unique_field = self.UNIQUE_FIELDS.get(table_name, "name")
                unique_value = data.get(unique_field)
                mongo_id = data.get("_mongo_id")

                if unique_value:
                    try:
                        # تحديث السجل الموجود
                        cursor.execute(
                            f"SELECT id FROM {table_name} WHERE {unique_field} = ?", (unique_value,)
                        )
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
                        cursor.execute(
                            f"SELECT id FROM {table_name} WHERE _mongo_id = ?", (mongo_id,)
                        )
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

        for table in self.TABLES:
            try:
                self._push_table_changes(table)
            except Exception as e:
                logger.error("❌ خطأ في رفع %s: %s", table, e)

    def _push_table_changes(self, table_name: str):
        """رفع تغييرات جدول واحد"""
        # ⚡ فحص الاتصال قبل استخدام MongoDB
        if self._shutdown:
            return

        if self.repo is None or not self.repo.online:
            return

        if self.repo.mongo_db is None or self.repo.mongo_client is None:
            logger.debug("تم تخطي رفع %s - MongoDB client غير متاح", table_name)
            return

        # ⚡ إنشاء cursor جديد لتجنب Recursive cursor error
        try:
            cursor = self.repo.get_cursor()
        except Exception as e:
            logger.debug("فشل إنشاء cursor: %s", e)
            return

        conn = self.repo.sqlite_conn
        unique_field = self.UNIQUE_FIELDS.get(table_name, "name")

        try:
            # جلب السجلات غير المتزامنة
            cursor.execute(
                f"""
                SELECT * FROM {table_name}
                WHERE sync_status != 'synced' OR sync_status IS NULL
            """
            )
            unsynced = cursor.fetchall()
        except Exception as e:
            logger.debug("فشل جلب السجلات غير المتزامنة: %s", e)
            cursor.close()
            return

        if not unsynced:
            cursor.close()
            return

        try:
            collection = self.repo.mongo_db[table_name]
        except Exception as e:
            if "Cannot use MongoClient after close" in str(e):
                logger.warning("⚠️ MongoDB client مغلق - تخطي رفع %s", table_name)
            cursor.close()
            return

        pushed = 0

        try:
            for row in unsynced:
                row_dict = dict(row)
                local_id = row_dict.get("id")
                mongo_id = row_dict.get("_mongo_id")
                unique_value = row_dict.get(unique_field)
                sync_status = row_dict.get("sync_status")

                if sync_status == "deleted":
                    try:
                        if mongo_id:
                            from bson import ObjectId

                            collection.delete_one({"_id": ObjectId(mongo_id)})
                        elif unique_value:
                            collection.delete_one({unique_field: unique_value})
                        cursor.execute(
                            f"DELETE FROM {table_name} WHERE id = ?",
                            (local_id,),
                        )
                        pushed += 1
                    except Exception as e:
                        logger.error("❌ فشل حذف %s/%s: %s", table_name, local_id, e)
                    continue

                cloud_data = self._prepare_data_for_cloud(row_dict)

                try:
                    if mongo_id:
                        from bson import ObjectId

                        collection.update_one({"_id": ObjectId(mongo_id)}, {"$set": cloud_data})
                    else:
                        # ⚡ فحص التكرار قبل الإدراج - معالجة خاصة للدفعات
                        existing = None

                        if table_name == "payments":
                            # البحث بـ (project_id + date + amount)
                            project_id = row_dict.get("project_id")
                            date = row_dict.get("date", "")
                            amount = row_dict.get("amount", 0)
                            date_short = str(date)[:10] if date else ""

                            if project_id and amount:
                                existing = collection.find_one(
                                    {
                                        "project_id": project_id,
                                        "amount": amount,
                                        "date": {"$regex": f"^{date_short}"},
                                    }
                                )
                        elif unique_value:
                            existing = collection.find_one({unique_field: unique_value})

                        if existing:
                            # ربط بالسجل الموجود
                            mongo_id = str(existing["_id"])
                            collection.update_one({"_id": existing["_id"]}, {"$set": cloud_data})
                        else:
                            # إدراج جديد
                            result = collection.insert_one(cloud_data)
                            mongo_id = str(result.inserted_id)

                    # تحديث السجل المحلي
                    cursor.execute(
                        f"UPDATE {table_name} SET _mongo_id = ?, sync_status = 'synced' WHERE id = ?",
                        (mongo_id, local_id),
                    )
                    pushed += 1

                except Exception as e:
                    # ⚡ تجاهل أخطاء التكرار
                    if "duplicate key" in str(e).lower() or "E11000" in str(e):
                        logger.debug("تجاهل سجل مكرر في %s: %s", table_name, e)
                        # تحديث حالة المزامنة على أي حال
                        cursor.execute(
                            f"UPDATE {table_name} SET sync_status = 'synced' WHERE id = ?",
                            (local_id,),
                        )
                    else:
                        logger.error("❌ فشل رفع %s/%s: %s", table_name, local_id, e)

            try:
                conn.commit()
            except Exception:
                pass

            if pushed > 0:
                logger.info("📤 %s: رفع %s سجل", table_name, pushed)

        finally:
            # ⚡ إغلاق الـ cursor
            try:
                cursor.close()
            except Exception:
                pass

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

                    existing_cloud = self.repo.mongo_db.users.find_one({"username": username})

                    if existing_cloud:
                        mongo_id = str(existing_cloud["_id"])
                        update_data = {
                            "full_name": user_data.get("full_name"),
                            "email": user_data.get("email"),
                            "role": user_data.get("role"),
                            "is_active": bool(user_data.get("is_active", 1)),
                            "last_modified": datetime.now(),
                        }
                        if user_data.get("password_hash"):
                            update_data["password_hash"] = user_data["password_hash"]

                        self.repo.mongo_db.users.update_one(
                            {"_id": existing_cloud["_id"]}, {"$set": update_data}
                        )
                        cursor.execute(
                            "UPDATE users SET _mongo_id=?, sync_status='synced' WHERE id=?",
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
                        }
                        result = self.repo.mongo_db.users.insert_one(new_user)
                        mongo_id = str(result.inserted_id)
                        cursor.execute(
                            "UPDATE users SET _mongo_id=?, sync_status='synced' WHERE id=?",
                            (mongo_id, local_id),
                        )
                        uploaded_count += 1

                if uploaded_count > 0:
                    conn.commit()
                    logger.info("📤 تم رفع %s مستخدم للسحابة", uploaded_count)

                # === 2. تنزيل المستخدمين من السحابة ===
                logger.info("📥 جاري تنزيل المستخدمين من السحابة...")
                cloud_users = list(self.repo.mongo_db.users.find())
                if not cloud_users:
                    return

                downloaded_count = 0
                for u in cloud_users:
                    mongo_id = str(u["_id"])
                    username = u.get("username")

                    for field in ["created_at", "last_modified", "last_login"]:
                        if field in u and hasattr(u[field], "isoformat"):
                            u[field] = u[field].isoformat()

                    cursor.execute(
                        "SELECT id, sync_status FROM users WHERE _mongo_id = ? OR username = ?",
                        (mongo_id, username),
                    )
                    exists = cursor.fetchone()

                    if exists:
                        if exists[1] not in ("modified_offline", "new_offline"):
                            cursor.execute(
                                """
                                UPDATE users SET
                                    full_name=?, email=?, role=?, is_active=?,
                                    password_hash=?, _mongo_id=?, sync_status='synced',
                                    last_modified=?
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
                                password_hash, is_active, sync_status, created_at, last_modified
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'synced', ?, ?)
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

                    # البحث عن التكرارات
                    cursor.execute(
                        f"""
                        SELECT {unique_field}, COUNT(*) as cnt, MIN(id) as keep_id
                        FROM {table}
                        WHERE {unique_field} IS NOT NULL
                        GROUP BY {unique_field}
                        HAVING cnt > 1
                    """
                    )
                    duplicates = cursor.fetchall()

                    deleted = 0
                    for dup in duplicates:
                        unique_value = dup[0]
                        keep_id = dup[2]

                        # حذف التكرارات (الاحتفاظ بالأقدم)
                        cursor.execute(
                            f"""
                            DELETE FROM {table}
                            WHERE {unique_field} = ? AND id != ?
                        """,
                            (unique_value, keep_id),
                        )
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
                    cursor.execute(f"DELETE FROM {table}")
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

        push_result = self.push_local_changes()
        pull_result = self.pull_remote_changes()

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
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    total = cursor.fetchone()[0]

                    cursor.execute(
                        f"""
                        SELECT COUNT(*) FROM {table}
                        WHERE sync_status != 'synced' OR sync_status IS NULL
                    """
                    )
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
                    self._watermarks = json.load(f)
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

    def push_local_changes(self) -> dict[str, Any]:
        """
        ⚡ Push all locally modified records to MongoDB
        Returns: dict with counts of pushed records and any errors
        """
        if self.repo is None or self.repo.sqlite_conn is None:
            return {"success": False, "reason": "sqlite_closed"}
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        results = {"success": True, "pushed": 0, "deleted": 0, "errors": 0}
        changed_tables: set[str] = set()

        try:
            cursor = self.repo.get_cursor()

            for table in self.TABLES:
                try:
                    before_pushed = results["pushed"]
                    before_deleted = results["deleted"]
                    # التحقق من وجود الجدول
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    )
                    if not cursor.fetchone():
                        continue

                    # جلب كل السجلات المحلية غير المتزامنة
                    # ملاحظة: بعض العمليات تضبط sync_status فقط بدون dirty_flag.
                    cursor.execute(
                        f"""
                        SELECT * FROM {table}
                        WHERE dirty_flag = 1
                           OR sync_status IS NULL
                           OR sync_status IN ('new_offline', 'modified_offline', 'pending', 'deleted')
                           OR _mongo_id IS NULL
                    """
                    )
                    dirty_records = cursor.fetchall()

                    if not dirty_records:
                        continue

                    columns = [desc[0] for desc in cursor.description]
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
                                now_dt = datetime.now()
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
                                cursor.execute(f"DELETE FROM {table} WHERE id = ?", (local_id,))
                                results["deleted"] += 1
                            else:
                                # Upsert إلى MongoDB
                                clean_record = {
                                    k: v
                                    for k, v in record.items()
                                    if k not in ["id", "sync_status", "dirty_flag", "is_deleted"]
                                }
                                clean_record["last_modified"] = datetime.now().isoformat()

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
                                    cursor.execute(
                                        f"UPDATE {table} SET _mongo_id = ? WHERE id = ?",
                                        (mongo_id, local_id),
                                    )

                                # تحديث dirty_flag و sync_status
                                cursor.execute(
                                    f"""
                                    UPDATE {table}
                                    SET dirty_flag = 0, sync_status = 'synced'
                                    WHERE id = ?
                                """,
                                    (local_id,),
                                )
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
        if self.repo is None or self.repo.sqlite_conn is None:
            return {"success": False, "reason": "sqlite_closed"}
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        if self._is_syncing:
            return {"success": False, "reason": "already_syncing"}

        results = {"success": True, "pulled": 0, "deleted": 0, "errors": 0}
        changed_tables: set[str] = set()

        try:
            cursor = self.repo.get_cursor()

            for table in self.TABLES:
                try:
                    before_pulled = results["pulled"]
                    before_deleted = results["deleted"]

                    # الحصول على Watermark لهذا الجدول
                    watermark = self._watermarks.get(table, "1970-01-01T00:00:00")
                    watermark_dt = self._parse_iso_datetime(watermark)
                    if watermark_dt and watermark_dt > datetime.now() + timedelta(seconds=30):
                        fallback_dt = datetime.now() - timedelta(minutes=5)
                        watermark = fallback_dt.isoformat()
                        self._watermarks[table] = watermark
                        self._save_watermarks()

                    # جلب السجلات من MongoDB المحدّثة بعد الـ watermark
                    collection = self.repo.mongo_db[table]
                    query = self._build_last_modified_query(watermark)
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
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    )
                    if not cursor.fetchone():
                        continue

                    # الحصول على أعمدة الجدول
                    cursor.execute(f"PRAGMA table_info({table})")
                    table_columns = {row[1] for row in cursor.fetchall()}

                    max_timestamp = watermark
                    logo_clients = 0

                    for remote in remote_records:
                        try:
                            mongo_id = str(remote["_id"])
                            is_deleted = remote.get("is_deleted", False)
                            last_modified_iso = self._to_iso_timestamp(
                                remote.get("last_modified", "")
                            )

                            # تحديث max_timestamp
                            if last_modified_iso and last_modified_iso > max_timestamp:
                                max_timestamp = last_modified_iso

                            # البحث عن السجل المحلي
                            cursor.execute(
                                f"SELECT id FROM {table} WHERE _mongo_id = ?", (mongo_id,)
                            )
                            local_row = cursor.fetchone()

                            if is_deleted:
                                # حذف من MongoDB -> حذف محلياً
                                if local_row:
                                    cursor.execute(
                                        f"DELETE FROM {table} WHERE id = ?", (local_row[0],)
                                    )
                                    results["deleted"] += 1
                            else:
                                # تحضير البيانات
                                item_data = self._prepare_cloud_data(remote, table_name=table)
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

                                if local_row:
                                    # تحديث السجل الموجود
                                    set_clause = ", ".join([f"{k} = ?" for k in filtered.keys()])
                                    values = list(filtered.values()) + [local_row[0]]
                                    cursor.execute(
                                        f"UPDATE {table} SET {set_clause} WHERE id = ?", values
                                    )
                                else:
                                    # إدراج سجل جديد
                                    cols = ", ".join(filtered.keys())
                                    placeholders = ", ".join(["?" for _ in filtered])
                                    cursor.execute(
                                        f"INSERT INTO {table} ({cols}) VALUES ({placeholders})",
                                        list(filtered.values()),
                                    )
                                results["pulled"] += 1

                        except Exception as e:
                            logger.debug("خطأ في سحب سجل من %s: %s", table, e)
                            results["errors"] += 1

                    if remote_records:
                        # ⚡ CRITICAL: Update watermark based on the LATEST record found
                        try:
                            latest_ts = max(
                                (
                                    self._to_iso_timestamp(r.get("last_modified", ""))
                                    for r in remote_records
                                ),
                                default="",
                            )
                            current_watermark = self._watermarks.get(table, "")

                            if latest_ts and latest_ts > current_watermark:
                                self._watermarks[table] = latest_ts
                                self._save_watermarks()  # ⚡ Save immediately
                                logger.debug("📍 Watermark updated for %s: %s", table, latest_ts)
                        except Exception as wm_err:
                            logger.error("❌ Failed to update watermark for %s: %s", table, wm_err)

                    self.repo.sqlite_conn.commit()
                    if table == "clients" and logo_clients > 0 and self._lazy_logo_enabled:
                        logger.info(
                            "📷 clients delta: %s عميل لديه شعار (metadata only - lazy mode)",
                            logo_clients,
                        )
                    if results["pulled"] > before_pulled or results["deleted"] > before_deleted:
                        changed_tables.add(table)

                except Exception as e:
                    logger.debug("خطأ في سحب جدول %s: %s", table, e)

            cursor.close()

            # حفظ الـ watermarks
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
        if self.repo is None or self.repo.sqlite_conn is None:
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
        if self.repo is None or self.repo.sqlite_conn is None:
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
            push_result = self.push_local_changes()
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
            next_run = time.monotonic()
            while not self._shutdown and not self._delta_thread_stop.is_set():
                next_run += interval_seconds
                sleep_for = max(0.0, next_run - time.monotonic())
                if sleep_for:
                    time.sleep(sleep_for)
                if self._shutdown or self._delta_thread_stop.is_set():
                    break
                if self._is_syncing or not self.is_online:
                    continue
                try:
                    self._run_delta_cycle()
                except Exception as e:
                    logger.debug("خطأ في periodic delta sync: %s", e)

        self._delta_thread = threading.Thread(
            target=delta_loop,
            daemon=True,
            name="unified-delta-sync",
        )
        self._delta_thread.start()

        logger.info("⏰ بدء Delta Sync كل %s ثانية", interval_seconds)


def create_unified_sync_manager(repository) -> UnifiedSyncManagerV3:
    """إنشاء مدير مزامنة موحد"""
    return UnifiedSyncManagerV3(repository)
