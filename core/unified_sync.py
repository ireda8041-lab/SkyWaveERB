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
from datetime import datetime
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

# ==================== ثوابت التوقيت (بالمللي ثانية) ====================
FULL_SYNC_INTERVAL_MS = 15 * 60 * 1000
QUICK_SYNC_INTERVAL_MS = 3 * 60 * 1000
CONNECTION_CHECK_INTERVAL_MS = 90 * 1000
CLOUD_PULL_INTERVAL_MS = 45 * 1000


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
        self._is_syncing = False
        self._max_retries = 3
        self._last_online_status = None
        self._shutdown = False  # ⚡ علامة الإغلاق
        self._last_full_sync_at = None

        # ⚡ إعدادات المزامنة التلقائية - مفعّلة للمزامنة بين الأجهزة
        self._auto_sync_enabled = True
        self._auto_sync_interval = FULL_SYNC_INTERVAL_MS
        self._quick_sync_interval = QUICK_SYNC_INTERVAL_MS
        self._connection_check_interval = CONNECTION_CHECK_INTERVAL_MS

        # ⚡ المؤقتات
        self._auto_sync_timer = None
        self._quick_sync_timer = None
        self._connection_timer = None
        self._cloud_pull_timer = None
        self._delta_pull_timer = None  # ⚡ NEW: مؤقت السحب التفاضلي

        # ⚡ Watermarks للـ Delta Sync
        self._watermarks: dict[str, str] = {}
        self._load_watermarks()

        logger.info("✅ تم تهيئة UnifiedSyncManager - مزامنة محسّنة للأداء")

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

        try:
            if table:
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
            return

        logger.info("🚀 بدء نظام المزامنة التلقائية...")

        # 1. مؤقت فحص الاتصال (كل دقيقة)
        self._connection_timer = QTimer(self)
        self._connection_timer.timeout.connect(self._check_connection)
        self._connection_timer.start(self._connection_check_interval)

        # 2. مؤقت المزامنة السريعة للتغييرات المحلية (كل دقيقة)
        self._quick_sync_timer = QTimer(self)
        self._quick_sync_timer.timeout.connect(self._quick_push_changes)
        self._quick_sync_timer.start(self._quick_sync_interval)

        # 3. مؤقت المزامنة الكاملة (كل 5 دقائق)
        self._auto_sync_timer = QTimer(self)
        self._auto_sync_timer.timeout.connect(self._auto_full_sync)
        self._auto_sync_timer.start(self._auto_sync_interval)

        self._cloud_pull_timer = QTimer(self)
        self._cloud_pull_timer.timeout.connect(self._cloud_pull_changes)
        self._cloud_pull_timer.start(CLOUD_PULL_INTERVAL_MS)

        # 4. مزامنة أولية بعد 5 ثواني
        QTimer.singleShot(5000, self._initial_sync)

        # 5. ⚡ NEW: بدء Delta Sync كل 60 ثانية للمزامنة بين الأجهزة
        self.start_delta_sync(interval_seconds=60)

        logger.info("⏰ المزامنة التلقائية: كل %s دقيقة", self._auto_sync_interval // 60000)
        logger.info("⏰ رفع التغييرات: كل %s دقيقة", self._quick_sync_interval // 60000)
        logger.info("⏰ Delta Sync: كل 60 ثانية")

    def stop_auto_sync(self):
        """⏹️ إيقاف نظام المزامنة التلقائية"""
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
                self._last_online_status = current_status
                try:
                    if not self._shutdown:
                        self.connection_changed.emit(current_status)
                except RuntimeError:
                    return  # Qt object deleted

                if current_status:
                    logger.info("🟢 تم استعادة الاتصال")
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
                self._last_full_sync_at = datetime.now()
                self.full_sync_from_cloud()
            except Exception as e:
                logger.debug("خطأ في المزامنة الخلفية: %s", e)

        threading.Thread(target=worker, daemon=True).start()

    def _cloud_pull_changes(self):
        if self._shutdown or not self.is_online:
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
            self.sync_error.emit(str(e))

        finally:
            self._is_syncing = False

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

                for i, cloud_item in enumerate(cloud_data):
                    self.sync_progress.emit(table_name, i + 1, len(cloud_data))

                    mongo_id = str(cloud_item["_id"])
                    cloud_mongo_ids.add(mongo_id)
                    unique_value = cloud_item.get(unique_field)

                    # تحضير البيانات
                    item_data = self._prepare_cloud_data(cloud_item)
                    item_data["_mongo_id"] = mongo_id
                    item_data["sync_status"] = "synced"

                    # البحث عن السجل المحلي
                    local_id = self._find_local_record(
                        cursor, table_name, mongo_id, unique_field, unique_value, table_columns
                    )

                    # تصفية الحقول
                    filtered = {k: v for k, v in item_data.items() if k in table_columns}

                    # ⚡ تسجيل لو logo_data موجود
                    if (
                        table_name == "clients"
                        and "logo_data" in item_data
                        and item_data["logo_data"]
                    ):
                        if "logo_data" in filtered:
                            logger.info(
                                "📷 [%s] logo_data سيتم حفظه (%s حرف)",
                                unique_value,
                                len(filtered["logo_data"]),
                            )
                        else:
                            logger.warning(
                                "⚠️ [%s] logo_data تم تجاهله! (غير موجود في أعمدة الجدول)",
                                unique_value,
                            )
                            logger.warning("   أعمدة الجدول: %s", table_columns)

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

                    # ⚡ إصلاح: تحديث الـ mongo_id إذا كان مختلف
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

    def _prepare_cloud_data(self, data: dict) -> dict:
        """تحضير بيانات السحابة للحفظ محلياً"""
        item = dict(data)
        item.pop("_id", None)
        item.pop("id", None)

        # ⚡ التأكد من جلب logo_data بشكل صحيح
        if "logo_data" in data and data["logo_data"]:
            item["logo_data"] = data["logo_data"]
            client_name = data.get("name", "غير معروف")
            logger.info(
                "📷 [%s] جلب logo_data (%s حرف) من السحابة",
                client_name,
                len(data["logo_data"]),
            )
            safe_print(
                f"INFO: 📷 [{client_name}] جلب logo_data ({len(data['logo_data'])} حرف) من السحابة"
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
                logger.info("📷 رفع logo_data (%s حرف) للسحابة", len(logo_data_value))
            elif not logo_path_value:
                # logo_data فارغ و logo_path فارغ = حذف صريح للصورة
                clean["logo_data"] = ""  # إرسال قيمة فارغة صريحة للحذف
                logger.info("🗑️ حذف logo_data من السحابة (حذف صريح)")
            else:
                # logo_data فارغ لكن logo_path موجود = لا نريد الكتابة فوق السحابة
                del clean["logo_data"]
                logger.debug("📷 تم تجاهل logo_data الفارغ (لن يتم الكتابة فوق السحابة)")

        if "logo_path" in clean and not clean["logo_path"]:
            # إذا كان logo_path فارغ، نرسل قيمة فارغة صريحة
            clean["logo_path"] = ""

        # تحويل التواريخ
        for field in [
            "created_at",
            "last_modified",
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

    def _load_watermarks(self):
        """تحميل Watermarks من ملف محلي"""
        try:
            from pathlib import Path

            # الحصول على مسار قاعدة البيانات
            if hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn:
                db_path = (
                    self.repo.sqlite_conn.database
                    if hasattr(self.repo.sqlite_conn, "database")
                    else None
                )
                if db_path:
                    watermark_file = Path(db_path).parent / "sync_watermarks.json"
                    if watermark_file.exists():
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
            from pathlib import Path

            if hasattr(self.repo, "sqlite_conn") and self.repo.sqlite_conn:
                db_path = (
                    self.repo.sqlite_conn.database
                    if hasattr(self.repo.sqlite_conn, "database")
                    else None
                )
                if db_path:
                    watermark_file = Path(db_path).parent / "sync_watermarks.json"
                    with open(watermark_file, "w", encoding="utf-8") as f:
                        json.dump(self._watermarks, f)
                    logger.debug("📍 تم حفظ Watermarks")
        except Exception as e:
            logger.debug("فشل حفظ Watermarks: %s", e)

    def push_local_changes(self) -> dict[str, Any]:
        """
        ⚡ Push all locally modified records (dirty_flag = 1) to MongoDB
        Returns: dict with counts of pushed records and any errors
        """
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        results = {"success": True, "pushed": 0, "deleted": 0, "errors": 0}

        try:
            cursor = self.repo.get_cursor()

            for table in self.TABLES:
                try:
                    # التحقق من وجود الجدول
                    cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    )
                    if not cursor.fetchone():
                        continue

                    # جلب السجلات المعلّمة بـ dirty_flag = 1
                    cursor.execute(
                        f"""
                        SELECT * FROM {table}
                        WHERE dirty_flag = 1 OR dirty_flag IS NULL AND sync_status = 'new_offline'
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
                            is_deleted = record.get("is_deleted", 0)

                            if is_deleted:
                                # Soft Delete: حذف من MongoDB ثم محلياً
                                if mongo_id:
                                    try:
                                        from bson import ObjectId

                                        # تحديث في MongoDB بـ is_deleted = True
                                        collection.update_one(
                                            {"_id": ObjectId(mongo_id)},
                                            {
                                                "$set": {
                                                    "is_deleted": True,
                                                    "last_modified": datetime.now().isoformat(),
                                                }
                                            },
                                        )
                                    except Exception as del_err:
                                        logger.debug("تجاهل خطأ حذف من MongoDB: %s", del_err)

                                # حذف محلياً (Hard Delete بعد المزامنة)
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
                                    from bson import ObjectId

                                    collection.update_one(
                                        {"_id": ObjectId(mongo_id)},
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

            cursor.close()

            if results["pushed"] > 0 or results["deleted"] > 0:
                logger.info("⬆️ Push: %s رفع, %s حذف", results["pushed"], results["deleted"])

        except Exception as e:
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
        if not self.is_online:
            return {"success": False, "reason": "offline"}

        if self._shutdown:
            return {"success": False, "reason": "shutdown"}

        if self._is_syncing:
            return {"success": False, "reason": "already_syncing"}

        results = {"success": True, "pulled": 0, "deleted": 0, "errors": 0}

        try:
            cursor = self.repo.get_cursor()

            for table in self.TABLES:
                try:
                    # الحصول على Watermark لهذا الجدول
                    watermark = self._watermarks.get(table, "1970-01-01T00:00:00")

                    # جلب السجلات من MongoDB المحدّثة بعد الـ watermark
                    collection = self.repo.mongo_db[table]
                    query = {"last_modified": {"$gt": watermark}}
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

                    for remote in remote_records:
                        try:
                            mongo_id = str(remote["_id"])
                            is_deleted = remote.get("is_deleted", False)
                            last_modified = remote.get("last_modified", "")

                            # تحديث max_timestamp
                            if last_modified and last_modified > max_timestamp:
                                max_timestamp = last_modified

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
                                item_data = self._prepare_cloud_data(remote)
                                item_data["_mongo_id"] = mongo_id
                                item_data["sync_status"] = "synced"
                                item_data["dirty_flag"] = 0
                                item_data["is_deleted"] = 0

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
                            latest_ts = max(r.get("last_modified", "") for r in remote_records)
                            current_watermark = self._watermarks.get(table, "")

                            if latest_ts and latest_ts > current_watermark:
                                self._watermarks[table] = latest_ts
                                self._save_watermarks()  # ⚡ Save immediately
                                logger.info("📍 Watermark updated for %s: %s", table, latest_ts)
                        except Exception as wm_err:
                            logger.error("❌ Failed to update watermark for %s: %s", table, wm_err)

                    self.repo.sqlite_conn.commit()

                except Exception as e:
                    logger.debug("خطأ في سحب جدول %s: %s", table, e)

            cursor.close()

            # حفظ الـ watermarks
            self._save_watermarks()

            if results["pulled"] > 0 or results["deleted"] > 0:
                logger.info("⬇️ Pull: %s سحب, %s حذف", results["pulled"], results["deleted"])
                # إرسال إشارة لتحديث الواجهة
                try:
                    self.data_synced.emit()
                except RuntimeError:
                    pass  # Qt object deleted

        except Exception as e:
            logger.error("❌ خطأ في pull_remote_changes: %s", e)
            results["success"] = False
            results["error"] = str(e)

        return results

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
                # رفع التغييرات المحلية أولاً
                self.push_local_changes()
                # سحب التغييرات من السيرفر
                self.pull_remote_changes()
            except Exception as e:
                logger.debug("خطأ في force_pull: %s", e)

        threading.Thread(target=pull_thread, daemon=True).start()

    def start_delta_sync(self, interval_seconds: int = 60):
        """
        ⚡ بدء نظام المزامنة التفاضلية (Delta Sync)
        يقوم بسحب التغييرات الجديدة كل فترة محددة
        """
        if self._delta_pull_timer:
            self._delta_pull_timer.stop()

        interval_ms = interval_seconds * 1000

        def periodic_delta_sync():
            if self._shutdown or self._is_syncing or not self.is_online:
                return

            def sync_thread():
                try:
                    self.push_local_changes()
                    self.pull_remote_changes()
                except Exception as e:
                    logger.debug("خطأ في periodic delta sync: %s", e)

            threading.Thread(target=sync_thread, daemon=True).start()

        self._delta_pull_timer = QTimer(self)
        self._delta_pull_timer.timeout.connect(periodic_delta_sync)
        self._delta_pull_timer.start(interval_ms)

        logger.info("⏰ بدء Delta Sync كل %s ثانية", interval_seconds)


def create_unified_sync_manager(repository) -> UnifiedSyncManagerV3:
    """إنشاء مدير مزامنة موحد"""
    return UnifiedSyncManagerV3(repository)
