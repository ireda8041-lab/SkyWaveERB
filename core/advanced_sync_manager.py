# الملف: core/advanced_sync_manager.py
"""
نظام المزامنة المتقدم - Offline-First مع Queue System
"""

import json
from datetime import datetime, timedelta
from typing import Any

import requests
from PyQt6.QtCore import QObject, QThread, pyqtSignal

from core.repository import Repository
from core.signals import app_signals

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class SyncQueueItem:
    """عنصر في قائمة انتظار المزامنة"""

    def __init__(self, action: str, table_name: str, data: dict[str, Any],
                 entity_id: str | None = None, priority: str = "medium"):
        self.id = None
        self.action = action  # create, update, delete
        self.table_name = table_name
        self.data = data
        self.entity_id = entity_id
        self.priority = priority  # high, medium, low
        self.timestamp = datetime.now()
        self.retry_count = 0
        self.max_retries = 3
        self.status = "pending"  # pending, syncing, completed, failed
        self.error_message = None


class ConnectionChecker(QThread):
    """فاحص الاتصال في الخلفية - معطّل للاستقرار"""

    connection_changed = pyqtSignal(bool)  # True = متصل, False = غير متصل

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_running = False  # ⚡ معطّل بشكل افتراضي
        self.check_interval = 60  # ⚡ دقيقة واحدة بدلاً من 10 ثواني
        self.last_status = None

    def run(self):
        """تشغيل فاحص الاتصال - معطّل للاستقرار"""
        # ⚡ معطّل - يسبب تجميد البرنامج
        safe_print("INFO: [ConnectionChecker] معطّل للاستقرار")
        return

        while self.is_running:
            try:
                # محاولة الاتصال بـ Google DNS
                response = requests.get("https://8.8.8.8", timeout=3)
                is_connected = response.status_code == 200
            except (requests.RequestException, OSError):
                is_connected = False

            # إرسال إشارة فقط عند تغيير الحالة
            if is_connected != self.last_status:
                try:
                    self.connection_changed.emit(is_connected)
                except RuntimeError:
                    return  # Qt object deleted
                self.last_status = is_connected

            # انتظار قبل الفحص التالي
            self.msleep(self.check_interval * 1000)

    def stop(self):
        """إيقاف فاحص الاتصال"""
        self.is_running = False
        try:
            self.quit()
            self.wait(500)  # ⚡ نصف ثانية فقط
        except RuntimeError:
            pass  # Qt object deleted


class SyncWorker(QThread):
    """عامل المزامنة في الخلفية - معطّل للاستقرار"""

    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(int, int)  # current, total
    sync_completed = pyqtSignal(dict)  # results
    sync_failed = pyqtSignal(str)  # error message
    item_synced = pyqtSignal(str)  # item id

    def __init__(self, repository: Repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.is_running = False  # ⚡ معطّل بشكل افتراضي
        self.sync_interval = 300  # ⚡ 5 دقائق بدلاً من دقيقة
        self.is_online = False

    def run(self):
        """تشغيل عامل المزامنة - معطّل للاستقرار"""
        # ⚡ معطّل - نظام المزامنة الموحد يقوم بالمهمة
        safe_print("INFO: [SyncWorker] معطّل للاستقرار - استخدم نظام المزامنة الموحد")
        return

        while self.is_running:
            if self.is_online:
                self.perform_sync()

            # انتظار قبل المحاولة التالية
            self.msleep(self.sync_interval * 1000)

    def set_online_status(self, is_online: bool):
        """تعيين حالة الاتصال"""
        self.is_online = is_online
        if is_online:
            # بدء المزامنة فوراً عند الاتصال
            self.perform_sync()

    def perform_sync(self):
        """تنفيذ المزامنة"""
        try:
            self.sync_started.emit()

            # جلب العناصر المعلقة
            pending_items = self._get_pending_sync_items()

            if not pending_items:
                self.sync_completed.emit({"synced": 0, "failed": 0})
                return

            synced_count = 0
            failed_count = 0

            for i, item in enumerate(pending_items):
                self.sync_progress.emit(i + 1, len(pending_items))

                try:
                    success = self._sync_item(item)
                    if success:
                        synced_count += 1
                        self.item_synced.emit(str(item.id))
                        self._mark_item_completed(item.id)
                    else:
                        failed_count += 1
                        self._increment_retry_count(item.id)

                except Exception as e:
                    safe_print(f"ERROR: [SyncWorker] Failed to sync item {item.id}: {e}")
                    failed_count += 1
                    self._mark_item_failed(item.id, str(e))

            # إرسال النتائج
            results = {
                "synced": synced_count,
                "failed": failed_count,
                "total": len(pending_items)
            }
            self.sync_completed.emit(results)

            # إرسال إشارة عامة
            if synced_count > 0:
                app_signals.sync_completed.emit(results)

        except Exception as e:
            safe_print(f"ERROR: [SyncWorker] Sync failed: {e}")
            self.sync_failed.emit(str(e))
            app_signals.sync_failed.emit(str(e))

    def _get_pending_sync_items(self) -> list[SyncQueueItem]:
        """جلب العناصر المعلقة للمزامنة"""
        try:
            self.repo.sqlite_cursor.execute("""
                SELECT id, COALESCE(action, operation) as action, entity_type as table_name, data, entity_id, priority,
                       created_at as timestamp, retry_count, status, error_message
                FROM sync_queue
                WHERE status = 'pending' AND retry_count < 3
                ORDER BY priority DESC, created_at ASC
                LIMIT 50
            """)

            rows = self.repo.sqlite_cursor.fetchall()
            items = []

            for row in rows:
                item = SyncQueueItem(
                    action=row['action'],
                    table_name=row['table_name'],
                    data=json.loads(row['data']),
                    entity_id=row['entity_id'],
                    priority=row['priority']
                )
                item.id = row['id']
                item.retry_count = row['retry_count']
                item.status = row['status']
                item.error_message = row['error_message']
                items.append(item)

            return items

        except Exception as e:
            safe_print(f"ERROR: [SyncWorker] Failed to get pending items: {e}")
            return []

    def _sync_item(self, item: SyncQueueItem) -> bool:
        """مزامنة عنصر واحد"""
        try:
            if not self.repo.online:
                return False

            collection = getattr(self.repo.mongo_db, item.table_name)

            if item.action == "create":
                result = collection.insert_one(item.data)
                return result.inserted_id is not None

            elif item.action == "update":
                if item.entity_id:
                    from bson import ObjectId
                    query: dict[str, Any] = {"_id": ObjectId(item.entity_id)} if ObjectId.is_valid(item.entity_id) else {"_mongo_id": item.entity_id}
                    result = collection.update_one(query, {"$set": item.data})
                    return bool(result.modified_count > 0)

            elif item.action == "delete":
                if item.entity_id:
                    from bson import ObjectId
                    query_del: dict[str, Any] = {"_id": ObjectId(item.entity_id)} if ObjectId.is_valid(item.entity_id) else {"_mongo_id": item.entity_id}
                    result = collection.delete_one(query_del)
                    return bool(result.deleted_count > 0)

            return False

        except Exception as e:
            safe_print(f"ERROR: [SyncWorker] Failed to sync item: {e}")
            return False

    def _mark_item_completed(self, item_id: int):
        """تمييز العنصر كمكتمل"""
        try:
            self.repo.sqlite_cursor.execute("""
                UPDATE sync_queue
                SET status = 'completed', last_attempt = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), item_id))
            self.repo.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [SyncWorker] Failed to mark item completed: {e}")

    def _mark_item_failed(self, item_id: int, error_message: str):
        """تمييز العنصر كفاشل"""
        try:
            self.repo.sqlite_cursor.execute("""
                UPDATE sync_queue
                SET status = 'failed', error_message = ?, last_attempt = ?
                WHERE id = ?
            """, (error_message, datetime.now().isoformat(), item_id))
            self.repo.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [SyncWorker] Failed to mark item failed: {e}")

    def _increment_retry_count(self, item_id: int):
        """زيادة عداد المحاولات"""
        try:
            self.repo.sqlite_cursor.execute("""
                UPDATE sync_queue
                SET retry_count = retry_count + 1, last_attempt = ?
                WHERE id = ?
            """, (datetime.now().isoformat(), item_id))
            self.repo.sqlite_conn.commit()
        except Exception as e:
            safe_print(f"ERROR: [SyncWorker] Failed to increment retry count: {e}")

    def stop(self):
        """إيقاف عامل المزامنة"""
        self.is_running = False
        try:
            self.quit()
            self.wait(500)  # ⚡ نصف ثانية فقط
        except RuntimeError:
            pass  # Qt object deleted


class AdvancedSyncManagerV3(QObject):
    """مدير المزامنة المتقدم - معطّل للاستقرار"""

    # إشارات
    connection_status_changed = pyqtSignal(bool)
    sync_status_changed = pyqtSignal(str)  # "syncing", "synced", "offline", "error"
    sync_progress = pyqtSignal(int, int)
    notification_ready = pyqtSignal(str, str)  # title, message

    def __init__(self, repository: Repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.is_online = False
        self.sync_status = "offline"

        # ⚡ لا نشغل الخيوط - معطّلة للاستقرار
        self.connection_checker = None
        self.sync_worker = None

        safe_print("INFO: [AdvancedSyncManager] معطّل للاستقرار - استخدم نظام المزامنة الموحد")

    def on_connection_changed(self, is_online: bool):
        """معالج تغيير حالة الاتصال"""
        self.is_online = is_online
        self.connection_status_changed.emit(is_online)

        # تحديث عامل المزامنة
        self.sync_worker.set_online_status(is_online)

        if is_online:
            self.sync_status = "syncing"
            self.notification_ready.emit("🟢 متصل", "تم استعادة الاتصال - جاري المزامنة...")
        else:
            self.sync_status = "offline"
            self.notification_ready.emit("🔴 غير متصل", "فقدان الاتصال - سيتم حفظ البيانات محلياً")

        self.sync_status_changed.emit(self.sync_status)

    def on_sync_started(self):
        """معالج بدء المزامنة"""
        self.sync_status = "syncing"
        self.sync_status_changed.emit(self.sync_status)

    def on_sync_completed(self, results: dict[str, int]):
        """معالج اكتمال المزامنة"""
        self.sync_status = "synced"
        self.sync_status_changed.emit(self.sync_status)

        synced = results.get("synced", 0)
        failed = results.get("failed", 0)

        if synced > 0:
            self.notification_ready.emit(
                "🚀 تمت المزامنة",
                f"تم رفع {synced} عملية بنجاح" + (f" ({failed} فشلت)" if failed > 0 else "")
            )

    def on_sync_failed(self, error_message: str):
        """معالج فشل المزامنة"""
        self.sync_status = "error"
        self.sync_status_changed.emit(self.sync_status)
        self.notification_ready.emit("❌ خطأ في المزامنة", error_message)

    def add_to_sync_queue(self, action: str, table_name: str, data: dict[str, Any],
                         entity_id: str | None = None, priority: str = "medium"):
        """إضافة عنصر إلى قائمة انتظار المزامنة"""
        try:
            now = datetime.now().isoformat()

            self.repo.sqlite_cursor.execute("""
                INSERT INTO sync_queue
                (operation, action, entity_type, data, entity_id, priority, created_at, last_modified, status, retry_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 0)
            """, (action, action, table_name, json.dumps(data), entity_id, priority, now, now))

            self.repo.sqlite_conn.commit()

            safe_print(f"INFO: [AdvancedSyncManager] Added to sync queue: {action} {table_name}")

            # إذا كان متصل، ابدأ المزامنة فوراً
            if self.is_online:
                self.sync_worker.perform_sync()

        except Exception as e:
            safe_print(f"ERROR: [AdvancedSyncManager] Failed to add to sync queue: {e}")

    def get_pending_count(self) -> int:
        """الحصول على عدد العناصر المعلقة"""
        try:
            self.repo.sqlite_cursor.execute("""
                SELECT COUNT(*) FROM sync_queue
                WHERE status = 'pending' AND retry_count < 3
            """)
            result = self.repo.sqlite_cursor.fetchone()
            return int(result[0]) if result else 0
        except Exception as e:
            safe_print(f"ERROR: [AdvancedSyncManager] Failed to get pending count: {e}")
            return 0

    def force_sync(self):
        """فرض المزامنة الفورية"""
        if self.is_online:
            self.sync_worker.perform_sync()
        else:
            self.notification_ready.emit("⚠️ غير متصل", "لا يمكن المزامنة بدون اتصال بالإنترنت")

    def get_sync_status(self) -> dict[str, Any]:
        """الحصول على حالة المزامنة"""
        return {
            "is_online": self.is_online,
            "sync_status": self.sync_status,
            "pending_count": self.get_pending_count()
        }

    def cleanup_completed_items(self, days_old: int = 7):
        """تنظيف العناصر المكتملة القديمة"""
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_old)).isoformat()

            self.repo.sqlite_cursor.execute("""
                DELETE FROM sync_queue
                WHERE status = 'completed' AND created_at < ?
            """, (cutoff_date,))

            deleted_count = self.repo.sqlite_cursor.rowcount
            self.repo.sqlite_conn.commit()

            if deleted_count > 0:
                safe_print(f"INFO: [AdvancedSyncManager] Cleaned up {deleted_count} old sync items")

        except Exception as e:
            safe_print(f"ERROR: [AdvancedSyncManager] Failed to cleanup: {e}")

    def stop(self):
        """إيقاف مدير المزامنة بأمان"""
        safe_print("INFO: [AdvancedSyncManager] Stopping...")
        try:
            if self.connection_checker is not None:
                self.connection_checker.stop()
        except Exception as e:
            safe_print(f"WARNING: [AdvancedSyncManager] Error stopping connection checker: {e}")
        try:
            if self.sync_worker is not None:
                self.sync_worker.stop()
        except Exception as e:
            safe_print(f"WARNING: [AdvancedSyncManager] Error stopping sync worker: {e}")
        safe_print("INFO: [AdvancedSyncManager] Stopped")

    def shutdown(self):
        """إغلاق مدير المزامنة"""
        safe_print("INFO: [AdvancedSyncManager] Shutting down...")

        self.stop()

        # تنظيف العناصر القديمة - فقط إذا كان الـ repo متاح
        try:
            if self.repo and hasattr(self.repo, 'sqlite_cursor') and self.repo.sqlite_cursor:
                self.cleanup_completed_items()
        except Exception as e:
            safe_print(f"WARNING: [AdvancedSyncManager] Cleanup skipped: {e}")

        safe_print("INFO: [AdvancedSyncManager] Shutdown complete")
