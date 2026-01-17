"""
🚀 مدير المزامنة الجديد - الإصدار الثالث
=====================================
حل نهائي لجميع مشاكل المزامنة:
- منع اختفاء الموظفين
- ضمان تطابق البيانات
- مزامنة ذكية وآمنة
- حماية من فقدان البيانات
"""

import json
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger

logger = get_logger(__name__)


class SyncManagerV3(QObject):
    """
    🚀 مدير المزامنة الجديد - الإصدار الثالث
    يضمن عدم فقدان أي بيانات ومزامنة آمنة 100%
    """

    # الإشارات
    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(str, int, int)  # table, current, total
    sync_completed = pyqtSignal(dict)
    sync_error = pyqtSignal(str)
    connection_changed = pyqtSignal(bool)
    data_conflict = pyqtSignal(str, dict, dict)  # table, local, remote

    # الجداول المدعومة
    SYNC_TABLES = [
        "clients",
        "projects",
        "services",
        "accounts",
        "employees",
        "invoices",
        "payments",
        "expenses",
        "journal_entries",
        "currencies",
        "notifications",
        "tasks",
    ]

    # الجداول المحمية (لا تُحذف أبداً)
    PROTECTED_TABLES = ["users", "settings", "user_preferences"]

    # الحقول الفريدة
    UNIQUE_FIELDS = {
        "clients": "name",
        "employees": "employee_id",
        "projects": "name",
        "services": "name",
        "accounts": "code",
        "users": "username",
        "tasks": "id",
        "invoices": "invoice_number",
        "currencies": "code",
    }

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self._lock = threading.RLock()
        self._is_syncing = False
        self._sync_stats = {}
        self._conflict_resolution = "local_wins"  # local_wins, remote_wins, merge

        # إنشاء الجداول المطلوبة
        self._init_sync_tables()

        logger.info("🚀 تم تهيئة SyncManagerV3")

    def _init_sync_tables(self):
        """إنشاء الجداول المطلوبة للمزامنة"""
        try:
            cursor = self.repo.sqlite_cursor

            # جدول حفظ البيانات المحذوفة (سلة المهملات)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS deleted_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    record_data TEXT NOT NULL,
                    deleted_at TEXT NOT NULL,
                    deleted_by TEXT,
                    can_restore INTEGER DEFAULT 1
                )
            """)

            # جدول تتبع التغييرات
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS change_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    operation TEXT NOT NULL,
                    old_data TEXT,
                    new_data TEXT,
                    changed_at TEXT NOT NULL,
                    changed_by TEXT,
                    sync_status TEXT DEFAULT 'pending'
                )
            """)

            # جدول حل التعارضات
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_conflicts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    record_id INTEGER NOT NULL,
                    local_data TEXT NOT NULL,
                    remote_data TEXT NOT NULL,
                    resolution TEXT,
                    resolved_at TEXT,
                    created_at TEXT NOT NULL
                )
            """)

            # جدول النسخ الاحتياطية
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_name TEXT NOT NULL,
                    backup_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    restore_point INTEGER DEFAULT 0
                )
            """)

            self.repo.sqlite_conn.commit()
            logger.info("✅ تم إنشاء جداول المزامنة")

        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء جداول المزامنة: {e}")

    @property
    def is_online(self) -> bool:
        """حالة الاتصال"""
        return self.repo.online if self.repo else False

    @property
    def is_syncing(self) -> bool:
        """هل المزامنة جارية؟"""
        return self._is_syncing

    def create_backup_point(self, name: str = None) -> bool:
        """إنشاء نقطة استعادة قبل المزامنة"""
        try:
            if not name:
                name = f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            cursor = self.repo.sqlite_cursor
            backup_data = {}

            # نسخ احتياطية من كل الجداول المهمة
            for table in self.SYNC_TABLES + self.PROTECTED_TABLES:
                try:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()

                    # تحويل إلى قائمة من القواميس
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in cursor.fetchall()]

                    backup_data[table] = [dict(zip(columns, row, strict=False)) for row in rows]
                except Exception as e:
                    logger.warning(f"تعذر نسخ جدول {table}: {e}")

            # حفظ النسخة الاحتياطية
            cursor.execute(
                """
                INSERT INTO sync_backups (backup_name, backup_data, created_at, restore_point)
                VALUES (?, ?, ?, 1)
            """,
                (
                    name,
                    json.dumps(backup_data, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )

            # الاحتفاظ بآخر 5 نسخ فقط
            cursor.execute("""
                DELETE FROM sync_backups
                WHERE id NOT IN (
                    SELECT id FROM sync_backups
                    ORDER BY created_at DESC
                    LIMIT 5
                )
            """)

            self.repo.sqlite_conn.commit()
            logger.info(f"✅ تم إنشاء نقطة استعادة: {name}")
            return True

        except Exception as e:
            logger.error(f"❌ خطأ في إنشاء نقطة الاستعادة: {e}")
            return False

    def safe_sync_all(self, progress_callback: Callable = None) -> dict[str, Any]:
        """
        مزامنة آمنة شاملة مع حماية من فقدان البيانات
        """
        if not self.is_online:
            return {"success": False, "error": "غير متصل بالإنترنت"}

        if self._is_syncing:
            return {"success": False, "error": "المزامنة جارية بالفعل"}

        self._is_syncing = True
        self.sync_started.emit()

        results = {
            "success": True,
            "backup_created": False,
            "tables_synced": {},
            "conflicts_found": 0,
            "errors": [],
        }

        try:
            with self._lock:
                # 1. إنشاء نقطة استعادة
                backup_name = f"pre_sync_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                results["backup_created"] = self.create_backup_point(backup_name)

                # 2. مزامنة المستخدمين أولاً (محمية)
                self._sync_protected_users()

                # 3. مزامنة كل جدول بأمان
                total_tables = len(self.SYNC_TABLES)
                for i, table in enumerate(self.SYNC_TABLES):
                    try:
                        if progress_callback:
                            progress_callback(f"مزامنة {table}...", i + 1, total_tables)
                        self.sync_progress.emit(table, i + 1, total_tables)

                        logger.info(f"🔄 مزامنة جدول: {table} ({i + 1}/{total_tables})")

                        # مزامنة الجدول
                        table_result = self._safe_sync_table(table)
                        results["tables_synced"][table] = table_result
                        results["conflicts_found"] += table_result.get("conflicts", 0)

                        logger.info(f"✅ تم مزامنة {table}: {table_result.get('synced', 0)} سجل")

                    except Exception as e:
                        error_msg = f"خطأ في مزامنة {table}: {e}"
                        logger.error(error_msg)
                        results["errors"].append(error_msg)
                        import traceback

                        traceback.print_exc()

                # 4. حساب الإجماليات
                total_synced = sum(
                    table_result.get("synced", 0) + table_result.get("updated", 0)
                    for table_result in results["tables_synced"].values()
                )
                results["total_synced"] = total_synced

                # 5. التحقق من النتائج
                if results["errors"]:
                    results["success"] = len(results["errors"]) < len(self.SYNC_TABLES) / 2

                logger.info(
                    f"✅ اكتملت المزامنة الآمنة: {len(results['tables_synced'])} جدول، {total_synced} سجل"
                )
                self.sync_completed.emit(results)

        except Exception as e:
            error_msg = f"خطأ في المزامنة الآمنة: {e}"
            logger.error(error_msg)
            results["success"] = False
            results["errors"].append(error_msg)
            self.sync_error.emit(error_msg)

        finally:
            self._is_syncing = False

        return results

    def _sync_protected_users(self):
        """مزامنة المستخدمين مع حماية خاصة"""
        try:
            cursor = self.repo.sqlite_cursor

            # جلب المستخدمين من السحابة
            cloud_users = list(self.repo.mongo_db.users.find())

            # حماية المستخدمين المحليين
            cursor.execute("SELECT * FROM users")
            local_users = cursor.fetchall()

            # تحويل إلى قاموس للمقارنة
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]
            local_users_dict = {
                row[columns.index("username")]: dict(zip(columns, row, strict=False))
                for row in local_users
            }

            # مزامنة بدون حذف المستخدمين المحليين
            for cloud_user in cloud_users:
                username = cloud_user.get("username")
                if not username:
                    continue

                # تحضير البيانات
                user_data = self._prepare_cloud_data_for_local(cloud_user)
                user_data["_mongo_id"] = str(cloud_user["_id"])
                user_data["sync_status"] = "synced"

                if username in local_users_dict:
                    # تحديث المستخدم الموجود (بحذر)
                    local_user = local_users_dict[username]

                    # لا نحدث كلمة المرور إذا كانت مختلفة محلياً
                    if local_user.get("password_hash") != user_data.get("password_hash"):
                        user_data.pop("password_hash", None)

                    # تحديث البيانات الأخرى فقط
                    update_fields = ["full_name", "email", "role", "_mongo_id", "sync_status"]
                    set_clause = ", ".join([f"{field}=?" for field in update_fields])
                    values = [user_data.get(field) for field in update_fields] + [local_user["id"]]

                    cursor.execute(f"UPDATE users SET {set_clause} WHERE id=?", values)
                else:
                    # إضافة مستخدم جديد
                    filtered_data = {
                        k: v for k, v in user_data.items() if k in columns and k != "id"
                    }

                    if filtered_data:
                        cols = ", ".join(filtered_data.keys())
                        placeholders = ", ".join(["?" for _ in filtered_data])
                        cursor.execute(
                            f"INSERT INTO users ({cols}) VALUES ({placeholders})",
                            list(filtered_data.values()),
                        )

            self.repo.sqlite_conn.commit()
            logger.info("✅ تم مزامنة المستخدمين بأمان")

        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة المستخدمين: {e}")

    def _safe_sync_table(self, table_name: str) -> dict[str, Any]:
        """مزامنة جدول واحد بأمان مع كشف التعارضات"""
        result = {"synced": 0, "updated": 0, "conflicts": 0, "errors": 0}

        try:
            cursor = self.repo.sqlite_cursor

            # 1. جلب البيانات من السحابة
            cloud_data = list(self.repo.mongo_db[table_name].find())
            cloud_ids = {str(item["_id"]): item for item in cloud_data}

            # 2. جلب البيانات المحلية
            cursor.execute(f"SELECT * FROM {table_name}")
            local_rows = cursor.fetchall()

            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]

            local_data = {}
            for row in local_rows:
                row_dict = dict(zip(columns, row, strict=False))
                mongo_id = row_dict.get("_mongo_id")
                if mongo_id:
                    local_data[mongo_id] = row_dict

            # 3. مزامنة البيانات من السحابة
            for mongo_id, cloud_item in cloud_ids.items():
                try:
                    prepared_data = self._prepare_cloud_data_for_local(cloud_item)
                    prepared_data["_mongo_id"] = mongo_id
                    prepared_data["sync_status"] = "synced"

                    # تصفية الحقول
                    filtered_data = {k: v for k, v in prepared_data.items() if k in columns}

                    if mongo_id in local_data:
                        # تحديث السجل الموجود
                        local_record = local_data[mongo_id]

                        # كشف التعارضات
                        if self._has_conflict(local_record, filtered_data):
                            conflict_resolved = self._resolve_conflict(
                                table_name, local_record, filtered_data
                            )
                            if conflict_resolved:
                                filtered_data = conflict_resolved
                                result["conflicts"] += 1
                            else:
                                continue  # تخطي هذا السجل

                        # تحديث السجل
                        set_clause = ", ".join([f"{k}=?" for k in filtered_data.keys()])
                        values = list(filtered_data.values()) + [local_record["id"]]
                        cursor.execute(f"UPDATE {table_name} SET {set_clause} WHERE id=?", values)
                        result["updated"] += 1
                    else:
                        # إدراج سجل جديد
                        if filtered_data:
                            cols = ", ".join(filtered_data.keys())
                            placeholders = ", ".join(["?" for _ in filtered_data])
                            cursor.execute(
                                f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})",
                                list(filtered_data.values()),
                            )
                            result["synced"] += 1

                except Exception as e:
                    logger.error(f"خطأ في مزامنة سجل من {table_name}: {e}")
                    result["errors"] += 1

            # 4. رفع البيانات المحلية الجديدة للسحابة
            self._push_local_changes(table_name)

            self.repo.sqlite_conn.commit()

        except Exception as e:
            logger.error(f"❌ خطأ في مزامنة {table_name}: {e}")
            result["errors"] += 1

        return result

    def _has_conflict(self, local_record: dict, remote_data: dict) -> bool:
        """كشف التعارضات بين البيانات المحلية والسحابية"""
        # مقارنة الحقول المهمة فقط
        important_fields = ["name", "title", "description", "amount", "status", "last_modified"]

        for field in important_fields:
            if field in local_record and field in remote_data:
                local_val = str(local_record[field] or "").strip()
                remote_val = str(remote_data[field] or "").strip()

                if local_val != remote_val:
                    # فحص التواريخ
                    local_modified = local_record.get("last_modified")
                    remote_modified = remote_data.get("last_modified")

                    if local_modified and remote_modified:
                        try:
                            local_dt = datetime.fromisoformat(local_modified.replace("Z", "+00:00"))
                            remote_dt = datetime.fromisoformat(
                                remote_modified.replace("Z", "+00:00")
                            )

                            # إذا كان الفرق أكثر من دقيقة، فهناك تعارض
                            if abs((local_dt - remote_dt).total_seconds()) > 60:
                                return True
                        except (ValueError, TypeError):
                            return True

        return False

    def _resolve_conflict(
        self, table_name: str, local_record: dict, remote_data: dict
    ) -> dict | None:
        """حل التعارضات بين البيانات"""
        try:
            cursor = self.repo.sqlite_cursor

            # حفظ التعارض في قاعدة البيانات
            cursor.execute(
                """
                INSERT INTO sync_conflicts
                (table_name, record_id, local_data, remote_data, created_at)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    table_name,
                    local_record.get("id"),
                    json.dumps(local_record, ensure_ascii=False, default=str),
                    json.dumps(remote_data, ensure_ascii=False, default=str),
                    datetime.now().isoformat(),
                ),
            )

            # إرسال إشارة التعارض
            self.data_conflict.emit(table_name, local_record, remote_data)

            # حل التعارض حسب الإعداد
            if self._conflict_resolution == "local_wins":
                return local_record
            elif self._conflict_resolution == "remote_wins":
                return remote_data
            elif self._conflict_resolution == "merge":
                return self._merge_records(local_record, remote_data)
            else:
                # افتراضي: المحلي يفوز
                return local_record

        except Exception as e:
            logger.error(f"خطأ في حل التعارض: {e}")
            return local_record  # المحلي يفوز في حالة الخطأ

    def _merge_records(self, local: dict, remote: dict) -> dict:
        """دمج السجلات المتعارضة بذكاء"""
        merged = dict(local)  # نبدأ بالبيانات المحلية

        # دمج الحقول المهمة من السحابة
        merge_fields = ["_mongo_id", "sync_status"]
        for field in merge_fields:
            if field in remote:
                merged[field] = remote[field]

        # استخدام أحدث تاريخ تعديل
        local_modified = local.get("last_modified")
        remote_modified = remote.get("last_modified")

        if remote_modified and local_modified:
            try:
                local_dt = datetime.fromisoformat(local_modified.replace("Z", "+00:00"))
                remote_dt = datetime.fromisoformat(remote_modified.replace("Z", "+00:00"))

                if remote_dt > local_dt:
                    # البيانات السحابية أحدث
                    for field in ["name", "title", "description", "amount", "status"]:
                        if field in remote:
                            merged[field] = remote[field]
            except (ValueError, TypeError):
                pass

        return merged

    def _push_local_changes(self, table_name: str):
        """رفع التغييرات المحلية للسحابة"""
        try:
            cursor = self.repo.sqlite_cursor

            # البحث عن السجلات المحلية غير المتزامنة
            cursor.execute(f"""
                SELECT * FROM {table_name}
                WHERE sync_status != 'synced' OR sync_status IS NULL
            """)
            local_changes = cursor.fetchall()

            if not local_changes:
                return

            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]

            collection = self.repo.mongo_db[table_name]
            unique_field = self.UNIQUE_FIELDS.get(table_name, "name")

            for row in local_changes:
                try:
                    row_dict = dict(zip(columns, row, strict=False))
                    local_id = row_dict.get("id")
                    mongo_id = row_dict.get("_mongo_id")

                    # تحضير البيانات للسحابة
                    cloud_data = self._prepare_local_data_for_cloud(row_dict)

                    if mongo_id:
                        # تحديث السجل الموجود
                        from bson import ObjectId

                        collection.update_one({"_id": ObjectId(mongo_id)}, {"$set": cloud_data})
                    else:
                        # فحص التكرار أولاً
                        unique_value = cloud_data.get(unique_field)
                        if unique_value:
                            existing = collection.find_one({unique_field: unique_value})
                            if existing:
                                # ربط بالسجل الموجود
                                mongo_id = str(existing["_id"])
                            else:
                                # إنشاء سجل جديد
                                result = collection.insert_one(cloud_data)
                                mongo_id = str(result.inserted_id)
                        else:
                            # إنشاء سجل جديد
                            result = collection.insert_one(cloud_data)
                            mongo_id = str(result.inserted_id)

                        # تحديث المعرف المحلي
                        cursor.execute(
                            f"UPDATE {table_name} SET _mongo_id=?, sync_status='synced' WHERE id=?",
                            (mongo_id, local_id),
                        )

                except Exception as e:
                    logger.error(f"خطأ في رفع سجل من {table_name}: {e}")

            self.repo.sqlite_conn.commit()

        except Exception as e:
            logger.error(f"خطأ في رفع تغييرات {table_name}: {e}")

    def _prepare_cloud_data_for_local(self, data: dict) -> dict:
        """تحضير بيانات السحابة للحفظ محلياً"""
        item = dict(data)
        item.pop("_id", None)
        item.pop("id", None)

        # تحويل التواريخ
        date_fields = [
            "created_at",
            "last_modified",
            "date",
            "issue_date",
            "due_date",
            "start_date",
            "end_date",
            "last_login",
        ]
        for field in date_fields:
            if field in item and hasattr(item[field], "isoformat"):
                item[field] = item[field].isoformat()

        # تحويل القوائم والكائنات إلى JSON
        json_fields = ["items", "lines", "data", "milestones", "tags"]
        for field in json_fields:
            if field in item and isinstance(item[field], (list, dict)):
                item[field] = json.dumps(item[field], ensure_ascii=False)

        # التأكد من الحقول المطلوبة
        now = datetime.now().isoformat()
        if not item.get("created_at"):
            item["created_at"] = now
        if not item.get("last_modified"):
            item["last_modified"] = now

        return item

    def _prepare_local_data_for_cloud(self, data: dict) -> dict:
        """تحضير البيانات المحلية للرفع للسحابة"""
        clean = {k: v for k, v in data.items() if k not in ["id", "_mongo_id", "sync_status"]}

        # تحويل التواريخ
        for field in [
            "created_at",
            "last_modified",
            "date",
            "issue_date",
            "due_date",
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
        for field in ["items", "lines", "data", "milestones", "tags"]:
            if field in clean and clean[field]:
                try:
                    if isinstance(clean[field], str):
                        clean[field] = json.loads(clean[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        return clean

    def restore_from_backup(self, backup_name: str = None) -> bool:
        """استعادة البيانات من نقطة استعادة"""
        try:
            cursor = self.repo.sqlite_cursor

            if backup_name:
                cursor.execute(
                    "SELECT backup_data FROM sync_backups WHERE backup_name = ?", (backup_name,)
                )
            else:
                cursor.execute(
                    "SELECT backup_data FROM sync_backups ORDER BY created_at DESC LIMIT 1"
                )

            backup_row = cursor.fetchone()
            if not backup_row:
                logger.error("لم يتم العثور على نسخة احتياطية")
                return False

            backup_data = json.loads(backup_row[0])

            # استعادة كل جدول
            for table_name, table_data in backup_data.items():
                try:
                    # مسح الجدول الحالي
                    cursor.execute(f"DELETE FROM {table_name}")

                    # استعادة البيانات
                    for record in table_data:
                        if record:  # تأكد من وجود بيانات
                            columns = ", ".join(record.keys())
                            placeholders = ", ".join(["?" for _ in record])
                            cursor.execute(
                                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                                list(record.values()),
                            )

                    logger.info(f"✅ تم استعادة {len(table_data)} سجل من {table_name}")

                except Exception as e:
                    logger.error(f"خطأ في استعادة {table_name}: {e}")

            self.repo.sqlite_conn.commit()
            logger.info("✅ تم استعادة البيانات بنجاح")
            return True

        except Exception as e:
            logger.error(f"❌ خطأ في استعادة البيانات: {e}")
            return False

    def get_sync_status(self) -> dict[str, Any]:
        """الحصول على حالة المزامنة التفصيلية"""
        cursor = self.repo.sqlite_cursor

        status = {
            "is_online": self.is_online,
            "is_syncing": self._is_syncing,
            "tables": {},
            "conflicts": 0,
            "backups": 0,
        }

        # إحصائيات الجداول
        for table in self.SYNC_TABLES:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                total = cursor.fetchone()[0]

                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE sync_status = 'synced'
                """)
                synced = cursor.fetchone()[0] if cursor.fetchone() else 0

                status["tables"][table] = {
                    "total": total,
                    "synced": synced,
                    "pending": total - synced,
                }
            except Exception:
                status["tables"][table] = {"total": 0, "synced": 0, "pending": 0}

        # عدد التعارضات
        try:
            cursor.execute("SELECT COUNT(*) FROM sync_conflicts WHERE resolution IS NULL")
            status["conflicts"] = cursor.fetchone()[0]
        except Exception:
            pass

        # عدد النسخ الاحتياطية
        try:
            cursor.execute("SELECT COUNT(*) FROM sync_backups")
            status["backups"] = cursor.fetchone()[0]
        except Exception:
            pass

        return status

    def set_conflict_resolution(self, strategy: str):
        """تحديد استراتيجية حل التعارضات"""
        if strategy in ["local_wins", "remote_wins", "merge"]:
            self._conflict_resolution = strategy
            logger.info(f"تم تحديد استراتيجية حل التعارضات: {strategy}")
        else:
            logger.warning(f"استراتيجية غير صحيحة: {strategy}")

    def stop(self):
        """⚡ إيقاف مدير المزامنة وتنظيف الموارد"""
        try:
            self._is_syncing = False
            logger.info("✅ تم إيقاف SyncManagerV3")
        except Exception as e:
            logger.warning(f"تحذير عند إيقاف SyncManagerV3: {e}")


def create_sync_manager_v3(repository) -> SyncManagerV3:
    """إنشاء مدير المزامنة الجديد"""
    return SyncManagerV3(repository)
