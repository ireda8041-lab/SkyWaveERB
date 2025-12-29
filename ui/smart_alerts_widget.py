# الملف: ui/smart_alerts_widget.py
"""
🔔 ويدجت التنبيهات الذكية - Sky Wave ERP
يعرض التنبيهات المهمة في الداشبورد مع:
- تصنيف حسب الأولوية
- إمكانية التأجيل
- التنقل للكيان المرتبط
- أنيميشن سلس عند الرفض/التأجيل
- تجميع حسب الفئة
"""

from datetime import datetime
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QMenu, QToolButton,
    QGraphicsOpacityEffect
)
from PyQt6.QtGui import QAction

from ui.styles import COLORS, BUTTON_STYLES


class AlertCard(QFrame):
    """كارت تنبيه واحد مع تصميم محسّن وأنيميشن"""
    
    dismissed = pyqtSignal(str)  # إشارة عند رفض التنبيه
    snoozed = pyqtSignal(str, int)  # إشارة عند تأجيل التنبيه (id, hours)
    action_clicked = pyqtSignal(str, str, str)  # إشارة عند الضغط على الإجراء
    
    # ألوان وأيقونات حسب الأولوية
    PRIORITY_STYLES = {
        'critical': {
            'color': '#ef4444',
            'bg': 'rgba(239, 68, 68, 0.15)',
            'hover_bg': 'rgba(239, 68, 68, 0.25)',
            'icon': '🚨',
            'border': '4px'
        },
        'high': {
            'color': '#f59e0b',
            'bg': 'rgba(245, 158, 11, 0.12)',
            'hover_bg': 'rgba(245, 158, 11, 0.2)',
            'icon': '⚠️',
            'border': '3px'
        },
        'medium': {
            'color': '#3b82f6',
            'bg': 'rgba(59, 130, 246, 0.1)',
            'hover_bg': 'rgba(59, 130, 246, 0.18)',
            'icon': 'ℹ️',
            'border': '3px'
        },
        'low': {
            'color': '#64748b',
            'bg': 'rgba(100, 116, 139, 0.08)',
            'hover_bg': 'rgba(100, 116, 139, 0.15)',
            'icon': '💡',
            'border': '2px'
        },
    }
    
    # أيقونات حسب نوع التنبيه
    TYPE_ICONS = {
        'project_overdue': '🚀',
        'project_due_soon': '📅',
        'project_no_payment': '💳',
        'invoice_overdue': '💰',
        'invoice_due_soon': '📄',
        'low_cash_balance': '🏦',
        'high_outstanding': '📊',
        'inactive_client': '👤',
        'expense_spike': '📈',
        'profit_margin_low': '📉',
        'task_overdue': '📋',
    }
    
    # وصف مختصر لكل نوع
    TYPE_LABELS = {
        'project_overdue': 'مشروع متأخر',
        'project_due_soon': 'موعد قريب',
        'project_no_payment': 'بدون دفعات',
        'invoice_overdue': 'مستحقات',
        'low_cash_balance': 'رصيد منخفض',
        'high_outstanding': 'مستحقات عالية',
        'inactive_client': 'عميل غير نشط',
        'expense_spike': 'ارتفاع مصروفات',
        'profit_margin_low': 'هامش ربح',
        'task_overdue': 'مهمة متأخرة',
    }
    
    def __init__(self, alert, parent=None):
        super().__init__(parent)
        self.alert = alert
        self.alert_id = alert.id
        
        priority = alert.priority.value
        style = self.PRIORITY_STYLES.get(priority, self.PRIORITY_STYLES['medium'])
        self.color = style['color']
        self.bg = style['bg']
        self.hover_bg = style['hover_bg']
        border = style['border']
        
        # أيقونة حسب النوع أو الأولوية
        icon = self.TYPE_ICONS.get(alert.type.value, style['icon'])
        
        self.setStyleSheet(f"""
            QFrame#alertCard {{
                background-color: {self.bg};
                border-radius: 10px;
                border-left: {border} solid {self.color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.setObjectName("alertCard")
        self.setMinimumHeight(80)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # تأثير الشفافية للأنيميشن
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self.opacity_effect)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(10)
        
        # الأيقونة مع خلفية دائرية
        icon_container = QFrame()
        icon_container.setFixedSize(38, 38)
        icon_container.setStyleSheet(f"""
            QFrame {{
                background-color: {self.color}20;
                border-radius: 19px;
            }}
        """)
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 18px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_layout.addWidget(icon_lbl)
        
        layout.addWidget(icon_container)
        
        # المحتوى
        content_layout = QVBoxLayout()
        content_layout.setSpacing(2)
        
        # الصف العلوي: العنوان + شارة النوع + الوقت
        top_row = QHBoxLayout()
        top_row.setSpacing(6)
        
        title_lbl = QLabel(alert.title)
        title_lbl.setStyleSheet(f"""
            color: {self.color};
            font-size: 12px;
            font-weight: bold;
            font-family: 'Cairo';
        """)
        top_row.addWidget(title_lbl)
        
        # شارة نوع التنبيه
        type_label = self.TYPE_LABELS.get(alert.type.value, '')
        if type_label:
            type_badge = QLabel(type_label)
            type_badge.setStyleSheet(f"""
                color: {self.color};
                font-size: 9px;
                font-family: 'Cairo';
                background-color: {self.color}18;
                padding: 1px 6px;
                border-radius: 6px;
            """)
            top_row.addWidget(type_badge)
        
        top_row.addStretch()
        
        # وقت الإنشاء
        if alert.created_at:
            time_str = self._format_time(alert.created_at)
            time_lbl = QLabel(time_str)
            time_lbl.setStyleSheet("""
                color: #475569;
                font-size: 9px;
                font-family: 'Cairo';
            """)
            top_row.addWidget(time_lbl)
        
        content_layout.addLayout(top_row)
        
        # الرسالة
        msg_lbl = QLabel(alert.message)
        msg_lbl.setStyleSheet("""
            color: #cbd5e1;
            font-size: 11px;
            font-family: 'Cairo';
        """)
        msg_lbl.setWordWrap(True)
        content_layout.addWidget(msg_lbl)
        
        # الصف السفلي: القيمة + معلومات إضافية
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(10)
        
        # القيمة (إذا وجدت)
        if alert.value and alert.value != 0:
            value_text = self._format_value(alert)
            if value_text:
                value_lbl = QLabel(value_text)
                value_lbl.setStyleSheet(f"""
                    color: {self.color};
                    font-size: 11px;
                    font-weight: bold;
                    font-family: 'Cairo';
                """)
                bottom_row.addWidget(value_lbl)
        
        # معلومات إضافية
        if hasattr(alert, 'extra_data') and alert.extra_data:
            extra_info = self._get_extra_info(alert)
            if extra_info:
                extra_lbl = QLabel(extra_info)
                extra_lbl.setStyleSheet("""
                    color: #64748b;
                    font-size: 9px;
                    font-family: 'Cairo';
                """)
                bottom_row.addWidget(extra_lbl)
        
        bottom_row.addStretch()
        content_layout.addLayout(bottom_row)
        
        layout.addLayout(content_layout, 1)
        
        # الأزرار
        buttons_layout = QVBoxLayout()
        buttons_layout.setSpacing(4)
        
        # زر الإجراء
        if alert.action_label:
            action_btn = QPushButton(alert.action_label)
            action_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {self.color};
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-size: 10px;
                    font-family: 'Cairo';
                    font-weight: bold;
                    min-width: 75px;
                }}
                QPushButton:hover {{
                    background-color: {self.color}dd;
                }}
            """)
            action_btn.clicked.connect(self._on_action_clicked)
            buttons_layout.addWidget(action_btn)
        
        # أزرار التحكم (رفض/تأجيل)
        control_layout = QHBoxLayout()
        control_layout.setSpacing(4)
        
        # زر التأجيل (قائمة منسدلة)
        snooze_btn = QToolButton()
        snooze_btn.setText("⏰")
        snooze_btn.setToolTip("تأجيل التنبيه")
        snooze_btn.setStyleSheet("""
            QToolButton {
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 4px;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #334155;
            }
        """)
        snooze_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        snooze_menu = QMenu(snooze_btn)
        snooze_menu.setStyleSheet("""
            QMenu {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 6px;
            }
            QMenu::item {
                color: #e2e8f0;
                padding: 8px 16px;
                border-radius: 4px;
                font-family: 'Cairo';
            }
            QMenu::item:selected {
                background-color: #334155;
            }
        """)
        
        snooze_menu.addAction("⏱️ ساعة واحدة", lambda: self._on_snooze(1))
        snooze_menu.addAction("🕓 4 ساعات", lambda: self._on_snooze(4))
        snooze_menu.addAction("📅 يوم كامل", lambda: self._on_snooze(24))
        snooze_menu.addAction("📆 أسبوع", lambda: self._on_snooze(168))
        
        snooze_btn.setMenu(snooze_menu)
        control_layout.addWidget(snooze_btn)
        
        # زر الرفض
        dismiss_btn = QPushButton("✕")
        dismiss_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #64748b;
                border: none;
                font-size: 14px;
                padding: 4px;
                min-width: 24px;
                max-width: 24px;
                border-radius: 4px;
            }
            QPushButton:hover {
                color: #ef4444;
                background-color: rgba(239, 68, 68, 0.1);
            }
        """)
        dismiss_btn.setToolTip("رفض التنبيه نهائياً")
        dismiss_btn.clicked.connect(self._on_dismiss)
        control_layout.addWidget(dismiss_btn)
        
        buttons_layout.addLayout(control_layout)
        layout.addLayout(buttons_layout)
    
    def enterEvent(self, event):
        """عند دخول الماوس"""
        self.setStyleSheet(f"""
            QFrame#alertCard {{
                background-color: {self.hover_bg};
                border-radius: 10px;
                border-left: 4px solid {self.color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """عند خروج الماوس"""
        self.setStyleSheet(f"""
            QFrame#alertCard {{
                background-color: {self.bg};
                border-radius: 10px;
                border-left: 4px solid {self.color};
            }}
            QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        super().leaveEvent(event)
    
    def _get_extra_info(self, alert) -> str:
        """استخراج معلومات إضافية"""
        extra = alert.extra_data
        if not extra:
            return ""
        
        parts = []
        if 'client' in extra and extra['client']:
            parts.append(f"العميل: {extra['client'][:12]}")
        if 'end_date' in extra:
            parts.append(f"الموعد: {extra['end_date']}")
        
        return " • ".join(parts[:2])
    
    def _format_time(self, dt: datetime) -> str:
        """تنسيق الوقت بشكل ذكي"""
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 7:
            return dt.strftime("%d/%m")
        elif diff.days > 0:
            return f"منذ {diff.days} يوم"
        elif diff.seconds > 3600:
            return f"منذ {diff.seconds // 3600} ساعة"
        elif diff.seconds > 60:
            return f"منذ {diff.seconds // 60} دقيقة"
        else:
            return "الآن"
    
    def _format_value(self, alert) -> str:
        """تنسيق القيمة حسب نوع التنبيه"""
        value = alert.value
        alert_type = alert.type.value
        
        if 'cash' in alert_type or 'outstanding' in alert_type or 'invoice' in alert_type or 'payment' in alert_type:
            if value >= 1000000:
                return f"💵 {value/1000000:,.1f}M ج.م"
            elif value >= 1000:
                return f"💵 {value/1000:,.1f}K ج.م"
            return f"💵 {value:,.0f} ج.م"
        elif 'overdue' in alert_type or 'due' in alert_type or 'inactive' in alert_type:
            days = int(value)
            if days == 1:
                return "📆 يوم واحد"
            elif days == 2:
                return "📆 يومان"
            elif days <= 10:
                return f"📆 {days} أيام"
            else:
                return f"📆 {days} يوم"
        elif 'spike' in alert_type or 'margin' in alert_type:
            return f"📊 {value:.1f}%"
        
        return ""
    
    def _on_dismiss(self):
        """عند رفض التنبيه مع أنيميشن"""
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.fade_animation.finished.connect(lambda: self.dismissed.emit(self.alert_id))
        self.fade_animation.start()
    
    def _on_snooze(self, hours: int):
        """عند تأجيل التنبيه مع أنيميشن"""
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.fade_animation.finished.connect(lambda: self.snoozed.emit(self.alert_id, hours))
        self.fade_animation.start()
    
    def _on_action_clicked(self):
        """عند الضغط على زر الإجراء"""
        self.action_clicked.emit(
            self.alert.type.value,
            self.alert.entity_type,
            self.alert.entity_id
        )


class SmartAlertsWidget(QFrame):
    """
    🔔 ويدجت التنبيهات الذكية
    يعرض قائمة التنبيهات المهمة مع تصنيف وتحكم كامل
    """
    
    alert_action = pyqtSignal(str, str, str)  # إشارة للتنقل للكيان المرتبط
    alerts_updated = pyqtSignal(int)  # إشارة عند تحديث عدد التنبيهات
    critical_alert = pyqtSignal(int)  # إشارة عند وجود تنبيهات حرجة
    
    def __init__(self, smart_alerts_service=None, parent=None):
        super().__init__(parent)
        self.alerts_service = smart_alerts_service
        self.alert_cards: list[AlertCard] = []
        self._is_expanded = True
        self._current_filter = "all"  # all, critical, high
        self._all_alerts = []  # كل التنبيهات قبل التصفية
        self._is_loading = False
        
        self.setStyleSheet("""
            QFrame#alertsWidget {
                background-color: #0f172a;
                border-radius: 12px;
                border: 1px solid #334155;
            }
        """)
        self.setObjectName("alertsWidget")
        self.setMinimumWidth(320)
        
        self.init_ui()
        
        # تحديث تلقائي كل 3 دقائق
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_alerts)
        self.refresh_timer.start(180000)
    
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)
        
        # الهيدر
        header_layout = QHBoxLayout()
        
        # أيقونة وعنوان
        title_layout = QHBoxLayout()
        title_layout.setSpacing(6)
        
        bell_icon = QLabel("🔔")
        bell_icon.setStyleSheet("font-size: 16px; background: transparent;")
        title_layout.addWidget(bell_icon)
        
        title = QLabel("التنبيهات الذكية")
        title.setStyleSheet("""
            color: white;
            font-size: 13px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """)
        title_layout.addWidget(title)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # عداد التنبيهات مع تصنيف
        self.count_container = QHBoxLayout()
        self.count_container.setSpacing(4)
        
        # عداد حرج
        self.critical_badge = QLabel("0")
        self.critical_badge.setStyleSheet("""
            background-color: #ef4444;
            color: white;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 8px;
            font-family: 'Cairo';
        """)
        self.critical_badge.setVisible(False)
        self.count_container.addWidget(self.critical_badge)
        
        # عداد عالي
        self.high_badge = QLabel("0")
        self.high_badge.setStyleSheet("""
            background-color: #f59e0b;
            color: white;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 8px;
            font-family: 'Cairo';
        """)
        self.high_badge.setVisible(False)
        self.count_container.addWidget(self.high_badge)
        
        # عداد إجمالي
        self.total_badge = QLabel("0")
        self.total_badge.setStyleSheet("""
            background-color: #3b82f6;
            color: white;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 8px;
            font-family: 'Cairo';
        """)
        self.count_container.addWidget(self.total_badge)
        
        header_layout.addLayout(self.count_container)
        
        # أزرار التصفية
        self.filter_container = QHBoxLayout()
        self.filter_container.setSpacing(2)
        
        filter_buttons = [
            ("الكل", "all", "#3b82f6"),
            ("🚨", "critical", "#ef4444"),
            ("⚠️", "high", "#f59e0b"),
        ]
        
        self.filter_btns = {}
        for label, filter_type, color in filter_buttons:
            btn = QPushButton(label)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: #64748b;
                    border: none;
                    font-size: 10px;
                    padding: 3px 6px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{
                    background-color: #334155;
                    color: white;
                }}
                QPushButton:checked {{
                    background-color: {color};
                    color: white;
                }}
            """)
            btn.setCheckable(True)
            btn.setChecked(filter_type == "all")
            btn.clicked.connect(lambda checked, ft=filter_type: self._on_filter_changed(ft))
            self.filter_container.addWidget(btn)
            self.filter_btns[filter_type] = btn
        
        header_layout.addLayout(self.filter_container)
        
        # زر التحديث
        refresh_btn = QPushButton("🔄")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-radius: 4px;
            }
        """)
        refresh_btn.setToolTip("تحديث التنبيهات")
        refresh_btn.clicked.connect(lambda: self.refresh_alerts(force=True))
        header_layout.addWidget(refresh_btn)
        
        # زر مسح كل التنبيهات المرفوضة
        clear_btn = QPushButton("🗑️")
        clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 12px;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #334155;
                border-radius: 4px;
            }
        """)
        clear_btn.setToolTip("إعادة عرض التنبيهات المرفوضة")
        clear_btn.clicked.connect(self._on_clear_dismissed)
        header_layout.addWidget(clear_btn)
        
        # زر طي/توسيع
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                font-size: 10px;
                padding: 4px;
                color: #64748b;
            }
            QPushButton:hover {
                color: white;
            }
        """)
        self.toggle_btn.clicked.connect(self._toggle_expand)
        header_layout.addWidget(self.toggle_btn)
        
        layout.addLayout(header_layout)
        
        # منطقة التنبيهات
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        
        # منطقة التمرير
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background-color: #1e293b;
                width: 6px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background-color: #475569;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #64748b;
            }
        """)
        scroll.setMaximumHeight(280)
        
        self.alerts_container = QWidget()
        self.alerts_container.setStyleSheet("background: transparent;")
        self.alerts_layout = QVBoxLayout(self.alerts_container)
        self.alerts_layout.setContentsMargins(0, 0, 0, 0)
        self.alerts_layout.setSpacing(6)
        self.alerts_layout.addStretch()
        
        scroll.setWidget(self.alerts_container)
        content_layout.addWidget(scroll)
        
        # رسالة عدم وجود تنبيهات
        self.no_alerts_widget = QFrame()
        self.no_alerts_widget.setStyleSheet("background: transparent;")
        no_alerts_layout = QVBoxLayout(self.no_alerts_widget)
        no_alerts_layout.setContentsMargins(10, 30, 10, 30)
        
        check_icon = QLabel("✅")
        check_icon.setStyleSheet("font-size: 32px; background: transparent;")
        check_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_alerts_layout.addWidget(check_icon)
        
        no_alerts_text = QLabel("كل شيء على ما يرام!")
        no_alerts_text.setStyleSheet("""
            color: #10b981;
            font-size: 13px;
            font-weight: bold;
            font-family: 'Cairo';
            background: transparent;
        """)
        no_alerts_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_alerts_layout.addWidget(no_alerts_text)
        
        no_alerts_sub = QLabel("لا توجد تنبيهات تحتاج انتباهك")
        no_alerts_sub.setStyleSheet("""
            color: #64748b;
            font-size: 11px;
            font-family: 'Cairo';
            background: transparent;
        """)
        no_alerts_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        no_alerts_layout.addWidget(no_alerts_sub)
        
        content_layout.addWidget(self.no_alerts_widget)
        self.no_alerts_widget.setVisible(True)
        
        layout.addWidget(self.content_widget)
    
    def _toggle_expand(self):
        """طي/توسيع قائمة التنبيهات"""
        self._is_expanded = not self._is_expanded
        self.content_widget.setVisible(self._is_expanded)
        self.toggle_btn.setText("▼" if self._is_expanded else "▶")
    
    def _on_filter_changed(self, filter_type: str):
        """عند تغيير فلتر التنبيهات"""
        self._current_filter = filter_type
        
        # تحديث حالة الأزرار
        for ft, btn in self.filter_btns.items():
            btn.setChecked(ft == filter_type)
        
        # إعادة عرض التنبيهات المفلترة
        self._display_filtered_alerts()
    
    def set_alerts_service(self, service):
        """تعيين خدمة التنبيهات"""
        self.alerts_service = service
        self.refresh_alerts()
    
    def refresh_alerts(self, force: bool = False):
        """تحديث التنبيهات"""
        if not self.alerts_service or self._is_loading:
            return
        
        self._is_loading = True
        
        try:
            # جلب التنبيهات
            alerts = self.alerts_service.check_all_alerts(force=force)
            self._all_alerts = alerts
            
            # عرض التنبيهات المفلترة
            self._display_filtered_alerts()
            
            # تحديث العدادات
            self._update_badges(alerts)
            
            # إرسال إشارة التحديث
            self.alerts_updated.emit(len(alerts))
            
            # إشارة التنبيهات الحرجة
            critical_count = sum(1 for a in alerts if a.priority.value == 'critical')
            if critical_count > 0:
                self.critical_alert.emit(critical_count)
            
            print(f"INFO: [SmartAlertsWidget] تم تحديث {len(alerts)} تنبيه")
            
        except Exception as e:
            print(f"ERROR: [SmartAlertsWidget] فشل تحديث التنبيهات: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self._is_loading = False
    
    def _display_filtered_alerts(self):
        """عرض التنبيهات حسب الفلتر الحالي"""
        # مسح التنبيهات القديمة
        for card in self.alert_cards:
            card.deleteLater()
        self.alert_cards.clear()
        
        # تصفية التنبيهات
        if self._current_filter == "all":
            filtered_alerts = self._all_alerts
        elif self._current_filter == "critical":
            filtered_alerts = [a for a in self._all_alerts if a.priority.value == 'critical']
        elif self._current_filter == "high":
            filtered_alerts = [a for a in self._all_alerts if a.priority.value in ('critical', 'high')]
        else:
            filtered_alerts = self._all_alerts
        
        # إضافة التنبيهات الجديدة
        for alert in filtered_alerts[:12]:  # أقصى 12 تنبيه
            card = AlertCard(alert)
            card.dismissed.connect(self._on_alert_dismissed)
            card.snoozed.connect(self._on_alert_snoozed)
            card.action_clicked.connect(self._on_alert_action)
            
            self.alerts_layout.insertWidget(self.alerts_layout.count() - 1, card)
            self.alert_cards.append(card)
        
        # إظهار/إخفاء رسالة عدم وجود تنبيهات
        has_alerts = len(filtered_alerts) > 0
        self.no_alerts_widget.setVisible(not has_alerts)
    
    def _update_badges(self, alerts: list):
        """تحديث شارات العدادات"""
        critical = sum(1 for a in alerts if a.priority.value == 'critical')
        high = sum(1 for a in alerts if a.priority.value == 'high')
        total = len(alerts)
        
        # عداد حرج
        self.critical_badge.setText(str(critical))
        self.critical_badge.setVisible(critical > 0)
        
        # عداد عالي
        self.high_badge.setText(str(high))
        self.high_badge.setVisible(high > 0 and critical == 0)
        
        # عداد إجمالي
        self.total_badge.setText(str(total))
        
        # تغيير لون العداد الإجمالي
        if critical > 0:
            self.total_badge.setStyleSheet("""
                background-color: #ef4444;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 8px;
                font-family: 'Cairo';
            """)
        elif high > 0:
            self.total_badge.setStyleSheet("""
                background-color: #f59e0b;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 8px;
                font-family: 'Cairo';
            """)
        elif total > 0:
            self.total_badge.setStyleSheet("""
                background-color: #3b82f6;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 8px;
                font-family: 'Cairo';
            """)
        else:
            self.total_badge.setStyleSheet("""
                background-color: #10b981;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 8px;
                font-family: 'Cairo';
            """)
    
    def _on_alert_dismissed(self, alert_id: str):
        """عند رفض تنبيه"""
        if self.alerts_service:
            self.alerts_service.dismiss_alert(alert_id)
        
        # إزالة من القائمة الكاملة
        self._all_alerts = [a for a in self._all_alerts if a.id != alert_id]
        
        # إزالة الكارت بأنيميشن
        for card in self.alert_cards:
            if card.alert_id == alert_id:
                card.deleteLater()
                self.alert_cards.remove(card)
                break
        
        # تحديث العدادات
        self._update_badges(self._all_alerts)
        self.no_alerts_widget.setVisible(len(self.alert_cards) == 0)
        self.alerts_updated.emit(len(self._all_alerts))
    
    def _on_alert_snoozed(self, alert_id: str, hours: int):
        """عند تأجيل تنبيه"""
        if self.alerts_service:
            self.alerts_service.snooze_alert(alert_id, hours)
        
        # إزالة من القائمة الكاملة
        self._all_alerts = [a for a in self._all_alerts if a.id != alert_id]
        
        # إزالة الكارت
        for card in self.alert_cards:
            if card.alert_id == alert_id:
                card.deleteLater()
                self.alert_cards.remove(card)
                break
        
        # تحديث العدادات
        self._update_badges(self._all_alerts)
        self.no_alerts_widget.setVisible(len(self.alert_cards) == 0)
    
    def _on_alert_action(self, alert_type: str, entity_type: str, entity_id: str):
        """عند الضغط على إجراء التنبيه"""
        self.alert_action.emit(alert_type, entity_type, entity_id)
    
    def get_alerts_count(self) -> int:
        """الحصول على عدد التنبيهات"""
        return len(self.alert_cards)
    
    def _on_clear_dismissed(self):
        """إعادة عرض التنبيهات المرفوضة"""
        if self.alerts_service:
            self.alerts_service.clear_all_dismissals()
            self.refresh_alerts(force=True)
    
    def get_critical_count(self) -> int:
        """الحصول على عدد التنبيهات الحرجة"""
        return sum(1 for a in self._all_alerts if a.priority.value == 'critical')
    
    def get_high_count(self) -> int:
        """الحصول على عدد التنبيهات العالية"""
        return sum(1 for a in self._all_alerts if a.priority.value == 'high')
