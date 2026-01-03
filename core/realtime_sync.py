# الملف: core/realtime_sync.py
"""
نظام المزامنة الفورية (Real-time) بين الأجهزة
- يستخدم MongoDB Change Streams للتحديث الفوري
- يرسل إشارات فورية عند تغيير البيانات
"""

import time
from datetime import datetime
from typing import Dict, Any, Optional
from threading import Thread, Event

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from pymongo.errors import PyMongoError

try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except:
            pass


class RealtimeSync(QObject):
    """نظام المزامنة الفورية"""
    
    # إشارات التحديث الفوري
    data_updated = pyqtSignal(str, dict)  # (collection_name, change_data)
    connection_status_changed = pyqtSignal(bool)  # (is_connected)
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.is_running = False
        self.watch_threads = {}
        self.stop_event = Event()
        
        # المجموعات المراد مراقبتها - جميع أقسام البرنامج
        self.collections_to_watch = [
            # إدارة المشاريع
            'projects',
            'project_items',
            'project_templates',
            
            # إدارة العملاء
            'clients',
            'client_contacts',
            
            # إدارة الخدمات
            'services',
            'service_categories',
            'service_templates',
            
            # إدارة المدفوعات والمالية
            'payments',
            'invoices',
            'quotes',
            'contracts',
            
            # إدارة المصروفات
            'expenses',
            'expense_categories',
            'expense_receipts',
            
            # المحاسبة
            'accounts',
            'journal_entries',
            'financial_reports',
            'budgets',
            
            # إدارة الموارد البشرية
            'employees',
            'departments',
            'attendance',
            'payroll',
            'leave_requests',
            
            # إدارة المخزون (إذا كان موجود)
            'inventory_items',
            'stock_movements',
            'suppliers',
            
            # النظام والإعدادات
            'users',
            'user_permissions',
            'system_settings',
            'notifications',
            'audit_logs',
            
            # التقارير والتحليلات
            'reports',
            'dashboards',
            'analytics_data',
            
            # الملفات والمرفقات
            'file_attachments',
            'document_templates',
            
            # المهام والتذكيرات
            'tasks',
            'reminders',
            'calendar_events'
        ]
        
        # تايمر للتحقق من الاتصال
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self._check_connection)
        self.connection_timer.start(5000)  # كل 5 ثواني
        
        self.last_connection_status = False
    
    def start(self):
        """بدء المزامنة الفورية"""
        if self.is_running:
            return
        
        if not self.repo or not self.repo.online or not self.repo.mongo_db:
            safe_print("WARNING: [RealtimeSync] MongoDB غير متاح - لا يمكن بدء المزامنة الفورية")
            return
        
        self.is_running = True
        self.stop_event.clear()
        
        safe_print("INFO: [RealtimeSync] بدء المزامنة الفورية...")
        
        # بدء مراقبة كل مجموعة في thread منفصل
        for collection_name in self.collections_to_watch:
            thread = Thread(
                target=self._watch_collection,
                args=(collection_name,),
                daemon=True,
                name=f"RealtimeSync-{collection_name}"
            )
            thread.start()
            self.watch_threads[collection_name] = thread
            safe_print(f"INFO: [RealtimeSync] بدء مراقبة {collection_name}")
    
    def stop(self):
        """إيقاف المزامنة الفورية"""
        if not self.is_running:
            return
        
        safe_print("INFO: [RealtimeSync] إيقاف المزامنة الفورية...")
        self.is_running = False
        self.stop_event.set()
        
        # انتظار انتهاء جميع الـ threads
        for collection_name, thread in self.watch_threads.items():
            if thread.is_alive():
                safe_print(f"INFO: [RealtimeSync] انتظار إيقاف مراقبة {collection_name}")
                thread.join(timeout=2)
        
        self.watch_threads.clear()
        self.connection_timer.stop()
        safe_print("INFO: [RealtimeSync] تم إيقاف المزامنة الفورية")
    
    def _watch_collection(self, collection_name: str):
        """مراقبة مجموعة واحدة للتغييرات"""
        try:
            collection = self.repo.mongo_db[collection_name]
            
            # إنشاء Change Stream
            with collection.watch(full_document='updateLookup') as stream:
                safe_print(f"INFO: [RealtimeSync] بدء مراقبة {collection_name}")
                
                for change in stream:
                    if self.stop_event.is_set():
                        break
                    
                    try:
                        self._handle_change(collection_name, change)
                    except Exception as e:
                        safe_print(f"ERROR: [RealtimeSync] خطأ في معالجة التغيير: {e}")
                        
        except PyMongoError as e:
            safe_print(f"ERROR: [RealtimeSync] خطأ MongoDB في {collection_name}: {e}")
        except Exception as e:
            safe_print(f"ERROR: [RealtimeSync] خطأ عام في مراقبة {collection_name}: {e}")
        finally:
            safe_print(f"INFO: [RealtimeSync] انتهت مراقبة {collection_name}")
    
    def _handle_change(self, collection_name: str, change: Dict[str, Any]):
        """معالجة تغيير في المجموعة"""
        try:
            operation_type = change.get('operationType')
            document_id = change.get('documentKey', {}).get('_id')
            
            safe_print(f"INFO: [RealtimeSync] تغيير في {collection_name}: {operation_type} - {document_id}")
            
            # إرسال إشارة التحديث
            change_data = {
                'operation': operation_type,
                'document_id': str(document_id) if document_id else None,
                'full_document': change.get('fullDocument'),
                'timestamp': datetime.now().isoformat()
            }
            
            self.data_updated.emit(collection_name, change_data)
            
        except Exception as e:
            safe_print(f"ERROR: [RealtimeSync] فشل معالجة التغيير: {e}")
    
    def _check_connection(self):
        """فحص حالة الاتصال"""
        try:
            is_connected = (
                self.repo and 
                self.repo.online and 
                self.repo.mongo_db and
                self.repo.mongo_db.admin.command('ping')
            )
            
            if is_connected != self.last_connection_status:
                self.last_connection_status = is_connected
                self.connection_status_changed.emit(is_connected)
                
                if is_connected:
                    safe_print("INFO: [RealtimeSync] ✅ الاتصال متاح")
                    if not self.is_running:
                        self.start()
                else:
                    safe_print("WARNING: [RealtimeSync] ❌ فقدان الاتصال")
                    if self.is_running:
                        self.stop()
                        
        except Exception as e:
            if self.last_connection_status:
                safe_print(f"WARNING: [RealtimeSync] فشل فحص الاتصال: {e}")
                self.last_connection_status = False
                self.connection_status_changed.emit(False)


class RealtimeDataManager(QObject):
    """مدير البيانات الفورية - يربط التحديثات بالواجهة"""
    
    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.realtime_sync = RealtimeSync(repository, self)
        
        # ربط الإشارات
        self.realtime_sync.data_updated.connect(self._on_data_updated)
        self.realtime_sync.connection_status_changed.connect(self._on_connection_changed)
    
    def start(self):
        """بدء المدير"""
        self.realtime_sync.start()
    
    def stop(self):
        """إيقاف المدير"""
        self.realtime_sync.stop()
    
    def _on_data_updated(self, collection_name: str, change_data: Dict[str, Any]):
        """معالجة تحديث البيانات"""
        try:
            # إرسال إشارة تحديث للواجهة
            from core.signals import app_signals
            
            # تحديد نوع البيانات المتغيرة - جميع أقسام البرنامج
            data_type_map = {
                # إدارة المشاريع
                'projects': 'projects',
                'project_items': 'projects',
                'project_templates': 'projects',
                
                # إدارة العملاء
                'clients': 'clients',
                'client_contacts': 'clients',
                
                # إدارة الخدمات
                'services': 'services',
                'service_categories': 'services',
                'service_templates': 'services',
                
                # إدارة المدفوعات والمالية
                'payments': 'payments',
                'invoices': 'invoices',
                'quotes': 'quotes',
                'contracts': 'contracts',
                
                # إدارة المصروفات
                'expenses': 'expenses',
                'expense_categories': 'expenses',
                'expense_receipts': 'expenses',
                
                # المحاسبة
                'accounts': 'accounting',
                'journal_entries': 'accounting',
                'financial_reports': 'accounting',
                'budgets': 'accounting',
                
                # إدارة الموارد البشرية
                'employees': 'hr',
                'departments': 'hr',
                'attendance': 'hr',
                'payroll': 'hr',
                'leave_requests': 'hr',
                
                # إدارة المخزون
                'inventory_items': 'inventory',
                'stock_movements': 'inventory',
                'suppliers': 'inventory',
                
                # النظام والإعدادات
                'users': 'system',
                'user_permissions': 'system',
                'system_settings': 'system',
                'notifications': 'notifications',
                'audit_logs': 'system',
                
                # التقارير والتحليلات
                'reports': 'reports',
                'dashboards': 'reports',
                'analytics_data': 'reports',
                
                # الملفات والمرفقات
                'file_attachments': 'files',
                'document_templates': 'files',
                
                # المهام والتذكيرات
                'tasks': 'tasks',
                'reminders': 'tasks',
                'calendar_events': 'tasks'
            }
            
            data_type = data_type_map.get(collection_name, collection_name)
            
            safe_print(f"INFO: [RealtimeDataManager] إرسال إشارة تحديث: {data_type} ({collection_name})")
            app_signals.emit_data_changed(data_type)
            
            # إشعارات مخصصة لكل قسم
            operation = change_data.get('operation', '')
            if operation in ['insert', 'update', 'delete']:
                self._send_section_notification(collection_name, operation, change_data)
                
        except Exception as e:
            safe_print(f"ERROR: [RealtimeDataManager] فشل معالجة التحديث: {e}")
    
    def _send_section_notification(self, collection_name: str, operation: str, change_data: dict):
        """إرسال إشعارات مخصصة لكل قسم"""
        try:
            from ui.notification_system import notify_info, notify_success, notify_warning
            
            operation_text = {
                'insert': 'إضافة',
                'update': 'تعديل', 
                'delete': 'حذف'
            }.get(operation, operation)
            
            document = change_data.get('full_document', {})
            
            # إشعارات مخصصة حسب القسم
            if collection_name == 'clients':
                client_name = document.get('name', 'عميل')
                if operation == 'update' and 'logo_data' in str(document):
                    notify_success(
                        f"تم تحديث لوجو العميل '{client_name}' 🖼️",
                        "👥 إدارة العملاء",
                        sync=False
                    )
                else:
                    notify_info(
                        f"تم {operation_text} العميل '{client_name}'",
                        "👥 إدارة العملاء",
                        sync=False
                    )
                    
            elif collection_name == 'projects':
                project_name = document.get('name', 'مشروع')
                notify_info(
                    f"تم {operation_text} المشروع '{project_name}'",
                    "📋 إدارة المشاريع",
                    sync=False
                )
                
            elif collection_name == 'services':
                service_name = document.get('name', 'خدمة')
                notify_info(
                    f"تم {operation_text} الخدمة '{service_name}'",
                    "🛠️ إدارة الخدمات",
                    sync=False
                )
                
            elif collection_name == 'payments':
                amount = document.get('amount', 0)
                notify_success(
                    f"تم {operation_text} دفعة بقيمة {amount} جنيه 💰",
                    "💳 إدارة المدفوعات",
                    sync=False
                )
                
            elif collection_name == 'expenses':
                category = document.get('category', 'مصروف')
                amount = document.get('amount', 0)
                notify_warning(
                    f"تم {operation_text} مصروف '{category}' بقيمة {amount} جنيه",
                    "💸 إدارة المصروفات",
                    sync=False
                )
                
            elif collection_name in ['accounts', 'journal_entries']:
                notify_info(
                    f"تم {operation_text} بيانات محاسبية",
                    "📊 المحاسبة",
                    sync=False
                )
                
            elif collection_name in ['employees', 'departments', 'attendance', 'payroll']:
                notify_info(
                    f"تم {operation_text} بيانات الموارد البشرية",
                    "👨‍💼 الموارد البشرية",
                    sync=False
                )
                
            elif collection_name in ['inventory_items', 'stock_movements', 'suppliers']:
                notify_info(
                    f"تم {operation_text} بيانات المخزون",
                    "📦 إدارة المخزون",
                    sync=False
                )
                
            elif collection_name in ['tasks', 'reminders', 'calendar_events']:
                notify_info(
                    f"تم {operation_text} مهمة أو تذكير",
                    "✅ المهام والتذكيرات",
                    sync=False
                )
                
            elif collection_name in ['reports', 'dashboards', 'analytics_data']:
                notify_info(
                    f"تم {operation_text} تقرير أو تحليل",
                    "📈 التقارير والتحليلات",
                    sync=False
                )
                
            elif collection_name in ['users', 'user_permissions', 'system_settings']:
                notify_warning(
                    f"تم {operation_text} إعدادات النظام",
                    "⚙️ إعدادات النظام",
                    sync=False
                )
                
            else:
                # إشعار عام للمجموعات الأخرى
                section_names = {
                    'invoices': '🧾 الفواتير',
                    'quotes': '💼 عروض الأسعار',
                    'contracts': '📄 العقود',
                    'file_attachments': '📎 المرفقات',
                    'document_templates': '📋 القوالب'
                }
                
                section_name = section_names.get(collection_name, f"📁 {collection_name}")
                notify_info(
                    f"تم {operation_text} بيانات",
                    section_name,
                    sync=False
                )
                
        except Exception as e:
            safe_print(f"ERROR: [RealtimeDataManager] فشل معالجة التحديث: {e}")
    
    def _on_connection_changed(self, is_connected: bool):
        """معالجة تغيير حالة الاتصال"""
        try:
            from ui.notification_system import notify_success, notify_warning
            from core.signals import app_signals
            
            # إرسال إشارة حالة المزامنة
            app_signals.emit_realtime_sync_status(is_connected)
            
            if is_connected:
                notify_success(
                    "تم الاتصال بالخادم - المزامنة الفورية نشطة لجميع الأقسام",
                    "🌐 المزامنة الفورية",
                    sync=False
                )
                safe_print("INFO: [RealtimeDataManager] ✅ المزامنة الفورية نشطة لجميع الأقسام")
            else:
                notify_warning(
                    "فقدان الاتصال بالخادم - المزامنة الفورية متوقفة",
                    "⚠️ المزامنة الفورية",
                    sync=False
                )
                safe_print("WARNING: [RealtimeDataManager] ❌ المزامنة الفورية متوقفة")
                
        except Exception as e:
            safe_print(f"ERROR: [RealtimeDataManager] فشل معالجة تغيير الاتصال: {e}")


# متغير عام للمدير
_realtime_manager: Optional[RealtimeDataManager] = None

def get_realtime_manager() -> Optional[RealtimeDataManager]:
    """الحصول على مدير المزامنة الفورية"""
    return _realtime_manager

def setup_realtime_sync(repository):
    """إعداد نظام المزامنة الفورية"""
    global _realtime_manager
    
    try:
        if _realtime_manager:
            _realtime_manager.stop()
        
        _realtime_manager = RealtimeDataManager(repository)
        _realtime_manager.start()
        
        safe_print("INFO: [RealtimeSync] ✅ تم إعداد نظام المزامنة الفورية")
        return _realtime_manager
        
    except Exception as e:
        safe_print(f"ERROR: [RealtimeSync] فشل إعداد المزامنة الفورية: {e}")
        return None

def shutdown_realtime_sync():
    """إغلاق نظام المزامنة الفورية"""
    global _realtime_manager
    
    if _realtime_manager:
        _realtime_manager.stop()
        _realtime_manager = None
        safe_print("INFO: [RealtimeSync] تم إغلاق نظام المزامنة الفورية")