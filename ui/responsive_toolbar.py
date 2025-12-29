# الملف: ui/responsive_toolbar.py
"""
شريط أدوات متجاوب - يعيد ترتيب الأزرار تلقائياً حسب المساحة المتاحة
باستخدام FlowLayout حقيقي
"""

from PyQt6.QtCore import Qt, QRect, QSize, QPoint
from PyQt6.QtWidgets import (
    QWidget,
    QLayout,
    QLayoutItem,
    QSizePolicy,
    QWidgetItem,
)


class FlowLayout(QLayout):
    """
    Layout يرتب العناصر تلقائياً في صفوف متعددة حسب المساحة المتاحة
    مثل CSS flexbox مع wrap
    """
    
    def __init__(self, parent=None, margin: int = 0, h_spacing: int = 5, v_spacing: int = 5):
        super().__init__(parent)
        self._items = []
        self._h_spacing = h_spacing
        self._v_spacing = v_spacing
        self.setContentsMargins(margin, margin, margin, margin)
    
    def addItem(self, item: QLayoutItem):
        self._items.append(item)
    
    def count(self) -> int:
        return len(self._items)
    
    def itemAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None
    
    def takeAt(self, index: int) -> QLayoutItem:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None
    
    def expandingDirections(self):
        return Qt.Orientation(0)
    
    def hasHeightForWidth(self) -> bool:
        return True
    
    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)
    
    def setGeometry(self, rect: QRect):
        super().setGeometry(rect)
        self._do_layout(rect, test_only=False)
    
    def sizeHint(self) -> QSize:
        return self.minimumSize()
    
    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        
        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size
    
    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        margins = self.contentsMargins()
        effective_rect = rect.adjusted(margins.left(), margins.top(), -margins.right(), -margins.bottom())
        
        x = effective_rect.x()
        y = effective_rect.y()
        line_height = 0
        
        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            
            space_x = self._h_spacing
            space_y = self._v_spacing
            
            next_x = x + item.sizeHint().width() + space_x
            
            # إذا تجاوز العرض، ننتقل لصف جديد
            if next_x - space_x > effective_rect.right() and line_height > 0:
                x = effective_rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            
            if not test_only:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))
            
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        
        return y + line_height - rect.y() + margins.bottom()


class ResponsiveToolbar(QWidget):
    """
    شريط أدوات متجاوب يرتب الأزرار تلقائياً في صفوف متعددة
    عند تصغير النافذة - باستخدام FlowLayout
    """
    
    def __init__(self, parent=None, spacing: int = 5):
        super().__init__(parent)
        
        # السياسة: يتمدد أفقياً، يتكيف عمودياً
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        
        # استخدام FlowLayout
        self._layout = FlowLayout(self, margin=0, h_spacing=spacing, v_spacing=spacing)
    
    def addButton(self, button):
        """إضافة زر للشريط"""
        self._layout.addWidget(button)
    
    def addWidget(self, widget):
        """إضافة widget عام (مثل checkbox)"""
        self._layout.addWidget(widget)
    
    def addStretch(self):
        """مساحة مرنة - غير مدعومة في FlowLayout"""
        pass
