# الملف: core/signal_manager.py
"""
🔗 مدير الإشارات المحسّن (Signal Manager)
يوفر إدارة آمنة للإشارات مع:
- تتبع الاتصالات
- فصل تلقائي عند الإغلاق
- Thread-safe signal emission
- حماية من Memory Leaks
"""

from __future__ import annotations

import threading
import weakref
from collections import defaultdict
from typing import Any, Callable

from PyQt6.QtCore import QMetaObject, QObject, Qt, pyqtSignal

from core.logger import get_logger

logger = get_logger(__name__)


class SignalConnection:
    """تمثيل اتصال إشارة واحد"""
    
    def __init__(
        self, 
        signal_name: str, 
        sender: QObject, 
        receiver: Callable,
        receiver_obj: QObject | None = None
    ):
        self.signal_name = signal_name
        self.sender_ref = weakref.ref(sender) if sender else None
        self.receiver = receiver
        self.receiver_obj_ref = weakref.ref(receiver_obj) if receiver_obj else None
        self.connected = True
    
    @property
    def sender(self) -> QObject | None:
        return self.sender_ref() if self.sender_ref else None
    
    @property
    def receiver_obj(self) -> QObject | None:
        return self.receiver_obj_ref() if self.receiver_obj_ref else None
    
    def is_valid(self) -> bool:
        """التحقق من صلاحية الاتصال"""
        if not self.connected:
            return False
        if self.sender_ref and self.sender_ref() is None:
            return False
        if self.receiver_obj_ref and self.receiver_obj_ref() is None:
            return False
        return True
    
    def disconnect(self) -> bool:
        """فصل الاتصال"""
        if not self.connected:
            return False
        
        try:
            sender = self.sender
            if sender is not None:
                signal = getattr(sender, self.signal_name, None)
                if signal is not None:
                    signal.disconnect(self.receiver)
            self.connected = False
            return True
        except (RuntimeError, TypeError) as e:
            logger.debug(f"تحذير عند فصل الإشارة: {e}")
            self.connected = False
            return False


class SignalManager:
    """
    مدير الإشارات المركزي
    
    يتتبع جميع اتصالات الإشارات ويوفر:
    - تسجيل الاتصالات
    - فصل تلقائي عند إغلاق النوافذ
    - تنظيف الاتصالات الميتة
    - إحصائيات الاتصالات
    
    الاستخدام:
        # تسجيل اتصال
        signal_manager.connect(
            sender=app_signals,
            signal_name='data_changed',
            receiver=self.on_data_changed,
            receiver_obj=self  # للتتبع والفصل التلقائي
        )
        
        # فصل كل اتصالات كائن معين
        signal_manager.disconnect_all(self)
    """
    
    _instance: SignalManager | None = None
    _lock = threading.Lock()
    
    def __new__(cls) -> SignalManager:
        """Singleton pattern"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._connections: dict[int, list[SignalConnection]] = defaultdict(list)
        self._all_connections: list[SignalConnection] = []
        self._connection_lock = threading.RLock()
        self._initialized = True
        logger.info("✅ تم تهيئة SignalManager")
    
    def connect(
        self,
        sender: QObject,
        signal_name: str,
        receiver: Callable,
        receiver_obj: QObject | None = None,
        connection_type: Qt.ConnectionType = Qt.ConnectionType.AutoConnection
    ) -> SignalConnection | None:
        """
        تسجيل اتصال إشارة مع تتبع
        
        Args:
            sender: الكائن المُرسل للإشارة
            signal_name: اسم الإشارة
            receiver: الدالة المستقبلة
            receiver_obj: الكائن المستقبل (للتتبع)
            connection_type: نوع الاتصال
            
        Returns:
            SignalConnection أو None في حالة الفشل
        """
        try:
            signal = getattr(sender, signal_name, None)
            if signal is None:
                logger.warning(f"⚠️ الإشارة غير موجودة: {signal_name}")
                return None
            
            # إنشاء الاتصال
            signal.connect(receiver, connection_type)
            
            # تسجيل الاتصال
            connection = SignalConnection(
                signal_name=signal_name,
                sender=sender,
                receiver=receiver,
                receiver_obj=receiver_obj
            )
            
            with self._connection_lock:
                self._all_connections.append(connection)
                if receiver_obj is not None:
                    obj_id = id(receiver_obj)
                    self._connections[obj_id].append(connection)
            
            logger.debug(f"🔗 تم تسجيل اتصال: {signal_name}")
            return connection
            
        except Exception as e:
            logger.error(f"❌ فشل تسجيل الاتصال: {e}")
            return None
    
    def disconnect_all(self, receiver_obj: QObject) -> int:
        """
        فصل جميع اتصالات كائن معين
        
        Args:
            receiver_obj: الكائن المراد فصل اتصالاته
            
        Returns:
            عدد الاتصالات التي تم فصلها
        """
        obj_id = id(receiver_obj)
        disconnected = 0
        
        with self._connection_lock:
            connections = self._connections.pop(obj_id, [])
            for conn in connections:
                if conn.disconnect():
                    disconnected += 1
        
        if disconnected > 0:
            logger.debug(f"🔌 تم فصل {disconnected} اتصال")
        
        return disconnected
    
    def cleanup_dead_connections(self) -> int:
        """
        تنظيف الاتصالات الميتة (الكائنات المحذوفة)
        
        Returns:
            عدد الاتصالات التي تم تنظيفها
        """
        cleaned = 0
        
        with self._connection_lock:
            # تنظيف القائمة الرئيسية
            valid_connections = []
            for conn in self._all_connections:
                if conn.is_valid():
                    valid_connections.append(conn)
                else:
                    conn.disconnect()
                    cleaned += 1
            self._all_connections = valid_connections
            
            # تنظيف القواميس
            dead_keys = []
            for obj_id, connections in self._connections.items():
                valid = [c for c in connections if c.is_valid()]
                if not valid:
                    dead_keys.append(obj_id)
                else:
                    self._connections[obj_id] = valid
            
            for key in dead_keys:
                del self._connections[key]
        
        if cleaned > 0:
            logger.debug(f"🧹 تم تنظيف {cleaned} اتصال ميت")
        
        return cleaned
    
    def get_connection_count(self, receiver_obj: QObject | None = None) -> int:
        """
        الحصول على عدد الاتصالات
        
        Args:
            receiver_obj: كائن معين (اختياري)
            
        Returns:
            عدد الاتصالات
        """
        with self._connection_lock:
            if receiver_obj is not None:
                return len(self._connections.get(id(receiver_obj), []))
            return len(self._all_connections)
    
    def get_stats(self) -> dict[str, Any]:
        """
        الحصول على إحصائيات الاتصالات
        
        Returns:
            dict مع الإحصائيات
        """
        with self._connection_lock:
            total = len(self._all_connections)
            valid = sum(1 for c in self._all_connections if c.is_valid())
            by_signal: dict[str, int] = defaultdict(int)
            
            for conn in self._all_connections:
                by_signal[conn.signal_name] += 1
            
            return {
                'total_connections': total,
                'valid_connections': valid,
                'dead_connections': total - valid,
                'tracked_objects': len(self._connections),
                'by_signal': dict(by_signal)
            }
    
    def disconnect_all_signals(self) -> int:
        """
        فصل جميع الاتصالات (عند إغلاق التطبيق)
        
        Returns:
            عدد الاتصالات التي تم فصلها
        """
        disconnected = 0
        
        with self._connection_lock:
            for conn in self._all_connections:
                if conn.disconnect():
                    disconnected += 1
            
            self._all_connections.clear()
            self._connections.clear()
        
        logger.info(f"🔌 تم فصل {disconnected} اتصال عند الإغلاق")
        return disconnected


class ThreadSafeSignalEmitter:
    """
    مُرسل إشارات آمن للـ threads
    
    يضمن إرسال الإشارات من الـ main thread حتى لو تم استدعاؤه من thread آخر
    
    الاستخدام:
        emitter = ThreadSafeSignalEmitter(app_signals)
        emitter.emit('data_changed', 'clients')  # آمن من أي thread
    """
    
    def __init__(self, signal_holder: QObject):
        self.signal_holder = signal_holder
        self._main_thread = threading.main_thread()
    
    def emit(self, signal_name: str, *args) -> bool:
        """
        إرسال إشارة بشكل آمن
        
        Args:
            signal_name: اسم الإشارة
            *args: معاملات الإشارة
            
        Returns:
            True إذا تم الإرسال بنجاح
        """
        try:
            signal = getattr(self.signal_holder, signal_name, None)
            if signal is None:
                logger.warning(f"⚠️ الإشارة غير موجودة: {signal_name}")
                return False
            
            # إذا كنا في الـ main thread، أرسل مباشرة
            if threading.current_thread() is self._main_thread:
                signal.emit(*args)
            else:
                # استخدم QMetaObject.invokeMethod للإرسال من thread آخر
                # هذا يضمن تنفيذ الإشارة في الـ main thread
                QMetaObject.invokeMethod(
                    self.signal_holder,
                    lambda: signal.emit(*args),
                    Qt.ConnectionType.QueuedConnection
                )
            
            return True
            
        except Exception as e:
            logger.error(f"❌ فشل إرسال الإشارة {signal_name}: {e}")
            return False
    
    def emit_queued(self, signal_name: str, *args) -> bool:
        """
        إرسال إشارة مع ضمان التنفيذ في الـ event loop التالي
        
        Args:
            signal_name: اسم الإشارة
            *args: معاملات الإشارة
            
        Returns:
            True إذا تم الإرسال بنجاح
        """
        try:
            from PyQt6.QtCore import QTimer
            
            signal = getattr(self.signal_holder, signal_name, None)
            if signal is None:
                return False
            
            # استخدم QTimer.singleShot لضمان التنفيذ في الـ main thread
            QTimer.singleShot(0, lambda: signal.emit(*args))
            return True
            
        except Exception as e:
            logger.error(f"❌ فشل إرسال الإشارة المؤجلة {signal_name}: {e}")
            return False


# Singleton instance
signal_manager = SignalManager()


def get_signal_manager() -> SignalManager:
    """الحصول على مدير الإشارات"""
    return signal_manager
