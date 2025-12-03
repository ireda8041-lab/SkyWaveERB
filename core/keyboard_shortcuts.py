# الملف: core/keyboard_shortcuts.py

"""
مدير اختصارات لوحة المفاتيح
يوفر اختصارات سريعة لتحسين الإنتاجية
"""

from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtCore import QObject, pyqtSignal
from typing import Dict, Callable
from core.logger import get_logger

logger = get_logger(__name__)


class KeyboardShortcutManager(QObject):
    """
    مدير اختصارات لوحة المفاتيح
    - تعريف الاختصارات
    - ربط الاختصارات بالإجراءات
    - إدارة الاختصارات المخصصة
    """
    
    # إشارات للاختصارات
    new_project = pyqtSignal()
    new_client = pyqtSignal()
    new_expense = pyqtSignal()
    search_activated = pyqtSignal()
    refresh_data = pyqtSignal()
    save_data = pyqtSignal()
    close_dialog = pyqtSignal()
    show_help = pyqtSignal()
    
    def __init__(self, main_window):
        """
        تهيئة مدير الاختصارات
        
        Args:
            main_window: النافذة الرئيسية للتطبيق
        """
        super().__init__()
        self.main_window = main_window
        self.shortcuts: Dict[str, QShortcut] = {}
        
        # تعريف الاختصارات
        self.shortcut_definitions = {
            # اختصارات الإنشاء
            'new_project': {
                'key': 'Ctrl+N',
                'description': 'مشروع جديد',
                'signal': self.new_project
            },
            'new_client': {
                'key': 'Ctrl+Shift+N',
                'description': 'عميل جديد',
                'signal': self.new_client
            },
            'new_expense': {
                'key': 'Ctrl+E',
                'description': 'مصروف جديد',
                'signal': self.new_expense
            },
            
            # اختصارات التنقل والبحث
            'search': {
                'key': 'Ctrl+F',
                'description': 'تفعيل البحث',
                'signal': self.search_activated
            },
            'refresh': {
                'key': 'F5',
                'description': 'تحديث البيانات',
                'signal': self.refresh_data
            },
            
            # اختصارات الحفظ والإغلاق
            'save': {
                'key': 'Ctrl+S',
                'description': 'حفظ',
                'signal': self.save_data
            },
            'close': {
                'key': 'Esc',
                'description': 'إغلاق النافذة',
                'signal': self.close_dialog
            },
            
            # اختصارات المساعدة
            'help': {
                'key': 'F1',
                'description': 'عرض المساعدة',
                'signal': self.show_help
            },
            
            # اختصارات التابات
            'tab_dashboard': {
                'key': 'Ctrl+1',
                'description': 'الانتقال إلى الداشبورد',
                'action': lambda: self._switch_tab(0)
            },
            'tab_projects': {
                'key': 'Ctrl+2',
                'description': 'الانتقال إلى المشاريع',
                'action': lambda: self._switch_tab(1)
            },
            'tab_quotations': {
                'key': 'Ctrl+3',
                'description': 'الانتقال إلى عروض الأسعار',
                'action': lambda: self._switch_tab(2)
            },
            'tab_expenses': {
                'key': 'Ctrl+4',
                'description': 'الانتقال إلى المصروفات',
                'action': lambda: self._switch_tab(3)
            },
            'tab_clients': {
                'key': 'Ctrl+5',
                'description': 'الانتقال إلى العملاء',
                'action': lambda: self._switch_tab(4)
            },
            'tab_services': {
                'key': 'Ctrl+6',
                'description': 'الانتقال إلى الخدمات',
                'action': lambda: self._switch_tab(5)
            },
            'tab_accounting': {
                'key': 'Ctrl+7',
                'description': 'الانتقال إلى المحاسبة',
                'action': lambda: self._switch_tab(6)
            },
            'tab_settings': {
                'key': 'Ctrl+8',
                'description': 'الانتقال إلى الإعدادات',
                'action': lambda: self._switch_tab(7)
            }
        }
        
        logger.info("تم تهيئة KeyboardShortcutManager")
    
    def setup_shortcuts(self):
        """إعداد جميع الاختصارات"""
        for name, definition in self.shortcut_definitions.items():
            self._create_shortcut(name, definition)
        
        logger.info(f"تم إعداد {len(self.shortcuts)} اختصار")
    
    def _create_shortcut(self, name: str, definition: Dict):
        """
        ⚡ إنشاء اختصار واحد بشكل احترافي
        
        Args:
            name: اسم الاختصار
            definition: تعريف الاختصار
        """
        try:
            shortcut = QShortcut(
                QKeySequence(definition['key']),
                self.main_window
            )
            
            # ⚡ تفعيل الاختصار دائماً
            shortcut.setEnabled(True)
            shortcut.setAutoRepeat(False)  # منع التكرار التلقائي
            
            # ربط الاختصار بالإجراء أو الإشارة
            if 'signal' in definition:
                shortcut.activated.connect(definition['signal'].emit)
            elif 'action' in definition:
                shortcut.activated.connect(definition['action'])
            
            self.shortcuts[name] = shortcut
            logger.debug(f"تم إنشاء اختصار: {name} ({definition['key']})")
        
        except Exception as e:
            logger.error(f"فشل إنشاء اختصار {name}: {e}")
    
    def _switch_tab(self, index: int):
        """
        التبديل إلى تاب معين
        
        Args:
            index: رقم التاب
        """
        try:
            if hasattr(self.main_window, 'tabs'):
                if index < self.main_window.tabs.count():
                    self.main_window.tabs.setCurrentIndex(index)
                    logger.debug(f"تم التبديل إلى التاب {index}")
        except Exception as e:
            logger.error(f"فشل التبديل إلى التاب {index}: {e}")
    
    def get_all_shortcuts(self) -> Dict[str, Dict]:
        """
        الحصول على جميع الاختصارات
        
        Returns:
            قاموس بجميع الاختصارات وتعريفاتها
        """
        return self.shortcut_definitions
    
    def get_shortcut_by_name(self, name: str) -> QShortcut:
        """
        الحصول على اختصار بالاسم
        
        Args:
            name: اسم الاختصار
            
        Returns:
            كائن QShortcut أو None
        """
        return self.shortcuts.get(name)
    
    def enable_shortcut(self, name: str):
        """
        تفعيل اختصار
        
        Args:
            name: اسم الاختصار
        """
        shortcut = self.shortcuts.get(name)
        if shortcut:
            shortcut.setEnabled(True)
            logger.debug(f"تم تفعيل الاختصار: {name}")
    
    def disable_shortcut(self, name: str):
        """
        تعطيل اختصار
        
        Args:
            name: اسم الاختصار
        """
        shortcut = self.shortcuts.get(name)
        if shortcut:
            shortcut.setEnabled(False)
            logger.debug(f"تم تعطيل الاختصار: {name}")
    
    def enable_all(self):
        """تفعيل جميع الاختصارات"""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(True)
        logger.info("تم تفعيل جميع الاختصارات")
    
    def disable_all(self):
        """تعطيل جميع الاختصارات"""
        for shortcut in self.shortcuts.values():
            shortcut.setEnabled(False)
        logger.info("تم تعطيل جميع الاختصارات")
    
    def get_shortcuts_by_category(self) -> Dict[str, list]:
        """
        الحصول على الاختصارات مصنفة حسب الفئة
        
        Returns:
            قاموس بالاختصارات مصنفة
        """
        categories = {
            'إنشاء': [],
            'تنقل وبحث': [],
            'حفظ وإغلاق': [],
            'مساعدة': [],
            'التابات': []
        }
        
        for name, definition in self.shortcut_definitions.items():
            if name.startswith('new_'):
                categories['إنشاء'].append({
                    'name': name,
                    'key': definition['key'],
                    'description': definition['description']
                })
            elif name in ['search', 'refresh']:
                categories['تنقل وبحث'].append({
                    'name': name,
                    'key': definition['key'],
                    'description': definition['description']
                })
            elif name in ['save', 'close']:
                categories['حفظ وإغلاق'].append({
                    'name': name,
                    'key': definition['key'],
                    'description': definition['description']
                })
            elif name == 'help':
                categories['مساعدة'].append({
                    'name': name,
                    'key': definition['key'],
                    'description': definition['description']
                })
            elif name.startswith('tab_'):
                categories['التابات'].append({
                    'name': name,
                    'key': definition['key'],
                    'description': definition['description']
                })
        
        return categories


# core/keyboard_shortcuts.py loaded
