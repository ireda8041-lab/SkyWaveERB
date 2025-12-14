# 🎨 نظام التصميم المتجاوب - Sky Wave ERP

## نظرة عامة

نظام تصميم موحد ومتجاوب يضمن تجربة مستخدم متسقة على جميع أحجام الشاشات.

## الملفات الرئيسية

- `ui/design_system.py` - نظام التصميم الأساسي
- `ui/styles.py` - الأنماط القديمة (للتوافق)
- `ui/example_responsive_dialog.py` - مثال على الاستخدام

## المكونات الرئيسية

### 1. الألوان (Colors)
```python
from ui.design_system import Colors

Colors.PRIMARY      # الأزرق الرئيسي
Colors.BG_DARK      # خلفية داكنة
Colors.TEXT_PRIMARY # نص أساسي
```

### 2. المسافات (Spacing)
```python
from ui.design_system import Spacing

Spacing.XS   # 4px
Spacing.SM   # 8px
Spacing.MD   # 12px
Spacing.LG   # 16px
Spacing.XL   # 24px
```

### 3. أحجام المكونات (ComponentSize)
```python
from ui.design_system import ComponentSize

ComponentSize.SMALL   # صغير
ComponentSize.MEDIUM  # متوسط
ComponentSize.LARGE   # كبير
```

## استخدام المصانع (Factories)

### ButtonFactory - إنشاء أزرار موحدة
```python
from ui.design_system import ButtonFactory, ComponentSize

btn = ButtonFactory.create_button(
    text="💾 حفظ",
    variant="primary",  # primary, success, warning, danger, secondary, ghost
    size=ComponentSize.MEDIUM
)
```

### InputFactory - أنماط الحقول
```python
from ui.design_system import InputFactory

input_field.setStyleSheet(InputFactory.get_input_style())
label.setStyleSheet(InputFactory.get_label_style())
```

### ContainerFactory - إنشاء حاويات
```python
from ui.design_system import ContainerFactory

card = ContainerFactory.create_card()
group = ContainerFactory.create_groupbox("عنوان المجموعة")
```

### DialogFactory - إعداد النوافذ المنبثقة
```python
from ui.design_system import DialogFactory

DialogFactory.setup_responsive_dialog(
    dialog=self,
    min_width=500,
    min_height=450,
    screen_ratio=0.6
)
```


## التخطيطات المتجاوبة (ResponsiveLayout)

### إنشاء تخطيطات
```python
from ui.design_system import ResponsiveLayout, Spacing

# تخطيط عمودي
vbox = ResponsiveLayout.create_vbox(spacing=Spacing.MD)

# تخطيط أفقي
hbox = ResponsiveLayout.create_hbox(spacing=Spacing.SM)

# تخطيط شبكي
grid = ResponsiveLayout.create_grid(columns=2)

# تخطيط نموذج
form = ResponsiveLayout.create_form_layout()
```

## سياسات الحجم (SizePolicies)

```python
from ui.design_system import SizePolicies

widget.setSizePolicy(SizePolicies.expanding())           # تمدد كامل
widget.setSizePolicy(SizePolicies.expanding_horizontal()) # تمدد أفقي
widget.setSizePolicy(SizePolicies.expanding_vertical())   # تمدد عمودي
widget.setSizePolicy(SizePolicies.fixed())               # ثابت
```

## القيم المتجاوبة

```python
from ui.design_system import get_responsive_value, get_screen_category

# الحصول على قيمة متجاوبة حسب حجم الشاشة
padding = get_responsive_value(
    mobile=8,
    tablet=12,
    desktop=16,
    large=20
)

# معرفة فئة الشاشة الحالية
category = get_screen_category()  # "mobile", "tablet", "laptop", "desktop", "large"
```

## مثال كامل على نافذة منبثقة

```python
from PyQt6.QtWidgets import QDialog, QLineEdit, QLabel
from ui.design_system import (
    DialogFactory, ContainerFactory, ButtonFactory, InputFactory,
    ResponsiveLayout, ResponsiveScrollArea, Spacing, ComponentSize,
    SizePolicies, Colors
)

class MyDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # إعداد النافذة المتجاوبة
        DialogFactory.setup_responsive_dialog(self, min_width=500, min_height=400)
        
        # التخطيط الرئيسي
        main_layout = ResponsiveLayout.create_vbox(spacing=Spacing.NONE)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(main_layout)
        
        # منطقة التمرير
        scroll = ResponsiveScrollArea()
        content = ContainerFactory.create_card()
        content_layout = ResponsiveLayout.create_vbox(spacing=Spacing.LG)
        
        # حقل إدخال
        row = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        self.input = QLineEdit()
        self.input.setStyleSheet(InputFactory.get_input_style())
        self.input.setSizePolicy(SizePolicies.expanding_horizontal())
        label = QLabel("الاسم:")
        label.setStyleSheet(InputFactory.get_label_style())
        row.addWidget(self.input, 1)
        row.addWidget(label, 0)
        content_layout.addLayout(row)
        
        content.setLayout(content_layout)
        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)
        
        # أزرار
        btn_container = ContainerFactory.create_card()
        btn_layout = ResponsiveLayout.create_hbox(spacing=Spacing.SM)
        btn_layout.addStretch()
        
        save_btn = ButtonFactory.create_button("💾 حفظ", "primary", ComponentSize.MEDIUM)
        btn_layout.addWidget(save_btn)
        
        btn_container.setLayout(btn_layout)
        main_layout.addWidget(btn_container)
```

## نقاط التوقف (Breakpoints)

| الفئة | العرض |
|-------|-------|
| Mobile | < 768px |
| Tablet | 768px - 1024px |
| Laptop | 1024px - 1280px |
| Desktop | 1280px - 1440px |
| Large | > 1440px |

## أفضل الممارسات

1. **استخدم `SizePolicies.expanding_horizontal()`** للحقول
2. **استخدم `ResponsiveLayout`** بدلاً من التخطيطات العادية
3. **استخدم `get_responsive_value()`** للقيم المتغيرة
4. **استخدم `DialogFactory.setup_responsive_dialog()`** للنوافذ المنبثقة
5. **تجنب الأحجام الثابتة** (`setFixedSize()`)
6. **استخدم `min-height` بدلاً من `height`** في CSS
