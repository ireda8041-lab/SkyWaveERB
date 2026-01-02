"""
صيانة قاعدة البيانات التلقائية
يتم تشغيلها تلقائياً عند بدء البرنامج
الإصدار المحسّن للأداء
"""

import sqlite3
from datetime import datetime
import json
import time

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class DatabaseMaintenance:
    """صيانة وإصلاح قاعدة البيانات تلقائياً"""
    
    def __init__(self, db_path: str = "skywave_local.db"):
        self.db_path = db_path
        self.db = None
        self.cursor = None
    
    def connect(self):
        """الاتصال بقاعدة البيانات مع تحسينات الأداء"""
        try:
            self.db = sqlite3.connect(self.db_path, timeout=30.0)
            self.cursor = self.db.cursor()
            # ⚡ تحسينات الأداء
            self.cursor.execute("PRAGMA journal_mode=WAL")
            self.cursor.execute("PRAGMA synchronous=NORMAL")
            self.cursor.execute("PRAGMA cache_size=5000")
            return True
        except Exception as e:
            safe_print(f"ERROR: [DBMaintenance] فشل الاتصال: {e}")
            return False
    
    def close(self):
        """إغلاق الاتصال"""
        if self.db:
            self.db.close()
    
    def run_all_maintenance(self):
        """تشغيل كل عمليات الصيانة - محسّن للسرعة"""
        if not self.connect():
            return False
        
        start_time = time.time()
        safe_print("\n" + "="*60)
        safe_print("🔧 [DBMaintenance] بدء صيانة قاعدة البيانات...")
        safe_print("="*60)
        
        try:
            # ⚡ تشغيل كل العمليات في transaction واحد للسرعة
            self.cursor.execute("BEGIN TRANSACTION")
            
            # 1. إضافة القيود
            self._add_unique_constraints()
            
            # 2. حذف التكرارات
            self._remove_duplicates()
            
            # 3. إصلاح أرقام الفواتير
            self._fix_invoice_numbers()
            
            # 4. تحديث حالة المزامنة
            self._fix_sync_status()
            
            # 5. تنظيف البيانات الفاسدة
            self._cleanup_corrupted_data()
            
            # ⚡ Commit كل التغييرات مرة واحدة
            self.db.commit()
            
            # ⚡ تحسين قاعدة البيانات
            self.cursor.execute("ANALYZE")
            
            elapsed = time.time() - start_time
            safe_print("="*60)
            safe_print(f"✅ [DBMaintenance] اكتملت الصيانة في {elapsed:.2f} ثانية")
            safe_print("="*60 + "\n")
            
            return True
            
        except Exception as e:
            self.db.rollback()
            safe_print(f"ERROR: [DBMaintenance] فشلت الصيانة: {e}")
            return False
        finally:
            self.close()
    
    def _add_unique_constraints(self):
        """إضافة قيود unique لمنع التكرار"""
        safe_print("📋 [1/5] إضافة قيود Unique...")
        
        constraints = [
            ("idx_projects_name", "projects", "name"),
            ("idx_projects_invoice", "projects", "invoice_number"),
            ("idx_clients_name", "clients", "name"),
            ("idx_services_name", "services", "name"),
        ]
        
        for idx_name, table, column in constraints:
            try:
                self.cursor.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS {idx_name} 
                    ON {table}({column})
                """)
            except Exception:
                pass  # Index already exists
        
        # Unique indexes for MongoDB IDs
        for table in ['projects', 'clients', 'services', 'payments']:
            try:
                self.cursor.execute(f"""
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_{table}_mongo_id 
                    ON {table}(_mongo_id) WHERE _mongo_id IS NOT NULL AND _mongo_id != ''
                """)
            except Exception:
                pass
        
        self.db.commit()
        safe_print("  ✅ تم إضافة القيود")
    
    def _remove_duplicates(self):
        """حذف السجلات المكررة - يحتفظ بالسجل الذي له _mongo_id أو الأقدم"""
        safe_print("📋 [2/5] حذف التكرارات...")
        
        total_deleted = 0
        
        # تعريف الجداول والحقول الفريدة
        tables_config = {
            'projects': 'name',
            'clients': 'name',
            'services': 'name',
            'accounts': 'code',
            'invoices': 'invoice_number',
            'currencies': 'code',
            'users': 'username',
            'expenses': 'id',  # للمصروفات نستخدم _mongo_id
            'notifications': 'id',
            'tasks': 'id',
        }
        
        for table, unique_field in tables_config.items():
            try:
                deleted = self._remove_table_duplicates_smart(table, unique_field)
                total_deleted += deleted
                if deleted > 0:
                    safe_print(f"  • حذف {deleted} سجل مكرر من {table}")
            except Exception as e:
                safe_print(f"  ⚠️ خطأ في حذف تكرارات {table}: {e}")
        
        # حذف الدفعات المكررة (بناءً على project_id + date + amount)
        try:
            self.cursor.execute("""
                DELETE FROM payments 
                WHERE id NOT IN (
                    SELECT MIN(CASE WHEN _mongo_id IS NOT NULL THEN id ELSE id + 1000000 END)
                    FROM payments 
                    GROUP BY project_id, date, amount
                )
            """)
            deleted = self.cursor.rowcount
            total_deleted += deleted
            if deleted > 0:
                safe_print(f"  • حذف {deleted} دفعة مكررة")
        except Exception as e:
            safe_print(f"  ⚠️ خطأ في حذف الدفعات: {e}")
        
        self.db.commit()
        
        if total_deleted == 0:
            safe_print("  ✅ لا توجد تكرارات")
        else:
            safe_print(f"  ✅ تم حذف {total_deleted} سجل مكرر")

    def _remove_table_duplicates_smart(self, table_name: str, unique_field: str) -> int:
        """
        حذف التكرارات من جدول معين بذكاء
        يحتفظ بالسجل الذي له _mongo_id، وإلا الأقدم
        """
        # البحث عن التكرارات
        self.cursor.execute(f"""
            SELECT {unique_field}, COUNT(*) as cnt
            FROM {table_name}
            WHERE {unique_field} IS NOT NULL AND {unique_field} != ''
            GROUP BY {unique_field}
            HAVING cnt > 1
        """)
        duplicates = self.cursor.fetchall()

        if not duplicates:
            return 0

        deleted = 0
        for dup in duplicates:
            unique_value = dup[0]

            # الحصول على كل السجلات المكررة مرتبة
            # الأولوية: 1. له _mongo_id  2. الأقدم (أقل id)
            self.cursor.execute(f"""
                SELECT id, _mongo_id FROM {table_name}
                WHERE {unique_field} = ?
                ORDER BY
                    CASE WHEN _mongo_id IS NOT NULL AND _mongo_id != '' THEN 0 ELSE 1 END,
                    id ASC
            """, (unique_value,))
            records = self.cursor.fetchall()

            # الاحتفاظ بالأول وحذف الباقي
            keep_id = records[0][0]
            for record in records[1:]:
                self.cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record[0],))
                deleted += 1

        return deleted
    
    def _fix_invoice_numbers(self):
        """إصلاح أرقام الفواتير المفقودة"""
        safe_print("📋 [3/5] إصلاح أرقام الفواتير...")
        
        try:
            self.cursor.execute("""
                SELECT id, name FROM projects 
                WHERE invoice_number IS NULL OR invoice_number = ''
            """)
            projects_without_invoice = self.cursor.fetchall()
            
            if not projects_without_invoice:
                safe_print("  ✅ جميع المشاريع لديها أرقام فواتير")
                return
            
            fixed_count = 0
            for project_id, project_name in projects_without_invoice:
                try:
                    # تحقق من وجود رقم محفوظ
                    self.cursor.execute(
                        "SELECT invoice_number FROM invoice_numbers WHERE project_name = ?",
                        (project_name,)
                    )
                    existing = self.cursor.fetchone()
                    
                    if existing:
                        invoice_number = existing[0]
                    else:
                        # ولّد رقم جديد
                        self.cursor.execute("SELECT MAX(id) FROM invoice_numbers")
                        max_id = self.cursor.fetchone()[0] or 0
                        new_seq = max_id + 1
                        invoice_number = f"SW-{97161 + new_seq}"
                        
                        # احفظ الرقم الجديد
                        self.cursor.execute(
                            "INSERT INTO invoice_numbers (project_name, invoice_number, created_at) VALUES (?, ?, ?)",
                            (project_name, invoice_number, datetime.now().isoformat())
                        )
                    
                    # حدّث المشروع
                    self.cursor.execute(
                        "UPDATE projects SET invoice_number = ? WHERE id = ?",
                        (invoice_number, project_id)
                    )
                    fixed_count += 1
                    
                except Exception as e:
                    safe_print(f"  ⚠️ فشل إصلاح {project_name}: {e}")
            
            self.db.commit()
            safe_print(f"  ✅ تم إصلاح {fixed_count} رقم فاتورة")
            
        except Exception as e:
            safe_print(f"  ⚠️ خطأ في إصلاح أرقام الفواتير: {e}")
    
    def _fix_sync_status(self):
        """تحديث حالة المزامنة"""
        safe_print("📋 [4/5] تحديث حالة المزامنة...")
        
        try:
            # تحديث المشاريع المتزامنة
            self.cursor.execute("""
                UPDATE projects 
                SET sync_status = 'synced' 
                WHERE _mongo_id IS NOT NULL 
                AND _mongo_id != '' 
                AND sync_status != 'synced'
            """)
            updated = self.cursor.rowcount
            
            # تحديث المشاريع المحلية
            self.cursor.execute("""
                UPDATE projects 
                SET sync_status = 'new_offline' 
                WHERE (_mongo_id IS NULL OR _mongo_id = '') 
                AND sync_status != 'new_offline'
            """)
            updated += self.cursor.rowcount
            
            self.db.commit()
            
            if updated > 0:
                safe_print(f"  ✅ تم تحديث {updated} سجل")
            else:
                safe_print("  ✅ حالة المزامنة صحيحة")
                
        except Exception as e:
            safe_print(f"  ⚠️ خطأ في تحديث حالة المزامنة: {e}")
    
    def _cleanup_corrupted_data(self):
        """تنظيف البيانات الفاسدة"""
        safe_print("📋 [5/5] تنظيف البيانات الفاسدة...")
        
        cleaned = 0
        
        try:
            # حذف المشاريع بدون اسم
            self.cursor.execute("DELETE FROM projects WHERE name IS NULL OR name = ''")
            cleaned += self.cursor.rowcount
            
            # حذف العملاء بدون اسم
            self.cursor.execute("DELETE FROM clients WHERE name IS NULL OR name = ''")
            cleaned += self.cursor.rowcount
            
            # إصلاح items الفاسدة في المشاريع
            self.cursor.execute("SELECT id, items FROM projects WHERE items IS NOT NULL")
            for row in self.cursor.fetchall():
                project_id, items = row
                if items and not items.startswith('['):
                    # items فاسدة، نصلحها
                    self.cursor.execute(
                        "UPDATE projects SET items = '[]' WHERE id = ?",
                        (project_id,)
                    )
                    cleaned += 1
            
            # ⚡ إصلاح قيود اليومية الفاسدة (إضافة account_id المفقود)
            self.cursor.execute("SELECT id, lines FROM journal_entries WHERE lines IS NOT NULL")
            for row in self.cursor.fetchall():
                entry_id, lines_json = row
                if lines_json:
                    try:
                        import json
                        lines = json.loads(lines_json) if isinstance(lines_json, str) else lines_json
                        needs_fix = False
                        for line in lines:
                            if isinstance(line, dict) and ("account_id" not in line or not line.get("account_id")):
                                line["account_id"] = line.get("account_code", "") or line.get("account_name", "") or "unknown"
                                needs_fix = True
                        if needs_fix:
                            self.cursor.execute(
                                "UPDATE journal_entries SET lines = ? WHERE id = ?",
                                (json.dumps(lines, ensure_ascii=False), entry_id)
                            )
                            cleaned += 1
                    except Exception:
                        pass
            
            self.db.commit()
            
            if cleaned > 0:
                safe_print(f"  ✅ تم تنظيف {cleaned} سجل")
            else:
                safe_print("  ✅ لا توجد بيانات فاسدة")
                
        except Exception as e:
            safe_print(f"  ⚠️ خطأ في التنظيف: {e}")


def run_maintenance():
    """دالة سريعة لتشغيل الصيانة"""
    maintenance = DatabaseMaintenance()
    return maintenance.run_all_maintenance()


# للاستخدام المباشر
if __name__ == "__main__":
    run_maintenance()
