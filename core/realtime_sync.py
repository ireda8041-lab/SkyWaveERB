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
        
        # المجموعات المراد مراقبتها - الأساسية فقط لتجنب البطء
        self.collections_to_watch = [
            'projects',
            'clients',
            'services',
            'payments',
            'expenses',
            'accounts',
            'notifications',
        ]
        
        # تايمر للتحقق من الاتصال - معطّل للاستقرار
        self.connection_timer = QTimer()
        # ⚡ لا نبدأ التايمر - المزامنة الفورية معطّلة
        # self.connection_timer.timeout.connect(self._check_connection)
        # self.connection_timer.start(60000)
        
        self.last_connection_status = False
        self._enabled = False  # ⚡ معطّل بشكل افتراضي
    
    def start(self):
        """بدء المزامنة الفورية - معطّل للاستقرار"""
        # ⚡ المزامنة الفورية معطّلة بشكل دائم - تسبب عدم استقرار
        # نظام المزامنة الموحد (unified_sync) يقوم بالمهمة بشكل أفضل
        safe_print("INFO: [RealtimeSync] المزامنة الفورية معطّلة - استخدم نظام المزامنة الموحد")
        return
    
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
        """مراقبة مجموعة واحدة للتغييرات - محسّنة ومحمية"""
        retry_count = 0
        max_retries = 3
        
        while not self.stop_event.is_set() and retry_count < max_retries and self._enabled:
            try:
                if not self.repo or not self.repo.online or self.repo.mongo_db is None:
                    time.sleep(5)
                    continue
                    
                collection = self.repo.mongo_db[collection_name]
                
                # إنشاء Change Stream مع timeout
                with collection.watch(
                    full_document='updateLookup',
                    max_await_time_ms=5000  # timeout 5 ثواني
                ) as stream:
                    safe_print(f"INFO: [RealtimeSync] بدء مراقبة {collection_name}")
                    retry_count = 0  # إعادة تعيين عداد المحاولات
                    
                    for change in stream:
                        if self.stop_event.is_set() or not self._enabled:
                            break
                        
                        try:
                            self._handle_change(collection_name, change)
                        except Exception as e:
                            safe_print(f"WARNING: [RealtimeSync] خطأ في معالجة التغيير: {e}")
                            
            except PyMongoError as e:
                retry_count += 1
                safe_print(f"WARNING: [RealtimeSync] خطأ MongoDB في {collection_name} (محاولة {retry_count}): {e}")
                if retry_count < max_retries:
                    time.sleep(10)  # انتظار 10 ثواني قبل إعادة المحاولة
            except Exception as e:
                retry_count += 1
                safe_print(f"WARNING: [RealtimeSync] خطأ عام في {collection_name} (محاولة {retry_count}): {e}")
                if retry_count < max_retries:
                    time.sleep(10)
                    
        safe_print(f"INFO: [RealtimeSync] انتهت مراقبة {collection_name}")
    
    def _handle_change(self, collection_name: str, change: Dict[str, Any]):
        """معالجة تغيير في المجموعة - محمية من الأخطاء"""
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
            
            # ⚡ إرسال الإشارة بشكل آمن
            try:
                self.data_updated.emit(collection_name, change_data)
            except RuntimeError:
                # Qt object deleted
                pass
            
        except Exception as e:
            # لا نُسقط البرنامج أبداً بسبب خطأ هنا
            safe_print(f"WARNING: [RealtimeSync] فشل معالجة التغيير: {e}")
    
    def _check_connection(self):
        """فحص حالة الاتصال - محسّن ومحمي"""
        if not self._enabled:
            return
            
        try:
            is_connected = False
            if self.repo and self.repo.online and self.repo.mongo_db is not None:
                try:
                    # فحص سريع بدون blocking
                    self.repo.mongo_db.admin.command('ping', maxTimeMS=3000)
                    is_connected = True
                except Exception:
                    is_connected = False
            
            if is_connected != self.last_connection_status:
                self.last_connection_status = is_connected
                self.connection_status_changed.emit(is_connected)
                
                if is_connected:
                    safe_print("INFO: [RealtimeSync] ✅ الاتصال متاح")
                    if not self.is_running and self._enabled:
                        self.start()
                else:
                    safe_print("WARNING: [RealtimeSync] ❌ فقدان الاتصال")
                        
        except Exception as e:
            # تجاهل الأخطاء - لا نريد crash
            pass


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
        """معالجة تحديث البيانات - محمية من الأخطاء"""
        try:
            # إرسال إشارة تحديث للواجهة
            from core.signals import app_signals
            
            # تحديد نوع البيانات المتغيرة - الأساسية فقط
            data_type_map = {
                'projects': 'projects',
                'clients': 'clients',
                'services': 'services',
                'payments': 'payments',
                'expenses': 'expenses',
                'accounts': 'accounting',
                'notifications': 'notifications',
            }
            
            data_type = data_type_map.get(collection_name, collection_name)
            
            safe_print(f"INFO: [RealtimeDataManager] إرسال إشارة تحديث: {data_type} ({collection_name})")
            
            # ⚡ إرسال الإشارة بشكل آمن
            try:
                app_signals.emit_data_changed(data_type)
            except RuntimeError:
                # Qt object deleted - تجاهل
                return
            
            # إشعارات مخصصة لكل قسم
            operation = change_data.get('operation', '')
            if operation in ['insert', 'update', 'delete']:
                self._send_section_notification(collection_name, operation, change_data)
                
        except Exception as e:
            # لا نُسقط البرنامج أبداً
            safe_print(f"WARNING: [RealtimeDataManager] فشل معالجة التحديث: {e}")
    
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