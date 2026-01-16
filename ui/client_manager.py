# الملف: ui/client_manager.py

import os

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import schemas
from services.client_service import ClientService
from ui.client_editor_dialog import ClientEditorDialog
from ui.styles import BUTTON_STYLES, get_cairo_font, TABLE_STYLE_DARK, create_centered_item

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:
    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class ClientManagerTab(QWidget):
    """
    (معدل) التاب الخاص بإدارة العملاء (مع عمود اللوجو)
    """

    def __init__(self, client_service: ClientService, parent=None):
        super().__init__(parent)

        self.client_service = client_service
        self.clients_list: list[schemas.Client] = []
        self.selected_client: schemas.Client | None = None

        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # جعل التاب متجاوب مع حجم الشاشة
        from PyQt6.QtWidgets import QSizePolicy
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # ⚡ الاستماع لإشارات تحديث البيانات (لتحديث الجدول أوتوماتيك)
        from core.signals import app_signals
        app_signals.clients_changed.connect(self._on_clients_changed)

        # === شريط الأزرار المتجاوب ===
        from ui.responsive_toolbar import ResponsiveToolbar
        self.toolbar = ResponsiveToolbar()

        self.add_button = QPushButton("➕ إضافة عميل جديد")
        self.add_button.setStyleSheet(BUTTON_STYLES["success"])
        self.add_button.setFixedHeight(28)
        self.add_button.clicked.connect(lambda: self.open_editor(client_to_edit=None))

        self.edit_button = QPushButton("✏️ تعديل العميل")
        self.edit_button.setStyleSheet(BUTTON_STYLES["warning"])
        self.edit_button.setFixedHeight(28)
        self.edit_button.clicked.connect(self.open_editor_for_selected)

        # زر الحذف الاحترافي
        self.delete_button = QPushButton("🗑️ حذف العميل")
        self.delete_button.setStyleSheet(BUTTON_STYLES["danger"])
        self.delete_button.setFixedHeight(28)
        self.delete_button.clicked.connect(self.delete_selected_client)
        self.delete_button.setEnabled(False)  # معطل حتى يتم اختيار عميل

        # زر التصدير
        self.export_button = QPushButton("📊 تصدير Excel")
        self.export_button.setStyleSheet(BUTTON_STYLES["success"])
        self.export_button.setFixedHeight(28)
        self.export_button.clicked.connect(self.export_clients)

        # زر الاستيراد
        self.import_button = QPushButton("📥 استيراد Excel")
        self.import_button.setStyleSheet(BUTTON_STYLES["info"])
        self.import_button.setFixedHeight(28)
        self.import_button.clicked.connect(self.import_clients)

        # زرار التحديث
        self.refresh_button = QPushButton("🔄 تحديث")
        self.refresh_button.setStyleSheet(BUTTON_STYLES["secondary"])
        self.refresh_button.setFixedHeight(28)
        self.refresh_button.clicked.connect(self.load_clients_data)

        self.show_archived_checkbox = QCheckBox("إظهار العملاء المؤرشفين")
        self.show_archived_checkbox.clicked.connect(self.load_clients_data)

        # إضافة الأزرار للـ toolbar المتجاوب
        self.toolbar.addButton(self.add_button)
        self.toolbar.addButton(self.edit_button)
        self.toolbar.addButton(self.delete_button)
        self.toolbar.addButton(self.export_button)
        self.toolbar.addButton(self.import_button)
        self.toolbar.addButton(self.refresh_button)
        self.toolbar.addWidget(self.show_archived_checkbox)

        main_layout.addWidget(self.toolbar)

        table_groupbox = QGroupBox("قايمة العملاء")
        table_layout = QVBoxLayout()
        table_groupbox.setLayout(table_layout)

        # استخدام الجدول العادي مع تفعيل الترتيب
        self.clients_table = QTableWidget()
        self.clients_table.setColumnCount(8)
        self.clients_table.setHorizontalHeaderLabels(["اللوجو", "الاسم", "الشركة", "الهاتف", "الإيميل", "💰 إجمالي المشاريع", "✅ إجمالي المدفوعات", "الحالة"])

        # ⚡ تفعيل الترتيب بالضغط على رأس العمود
        self.clients_table.setSortingEnabled(True)

        # === UNIVERSAL SEARCH BAR ===
        from ui.universal_search import UniversalSearchBar
        self.search_bar = UniversalSearchBar(
            self.clients_table,
            placeholder="🔍 بحث (الاسم، الشركة، الهاتف، الإيميل)..."
        )
        table_layout.addWidget(self.search_bar)
        # === END SEARCH BAR ===

        self.clients_table.setStyleSheet(TABLE_STYLE_DARK)
        # إصلاح مشكلة انعكاس الأعمدة في RTL
        from ui.styles import fix_table_rtl
        fix_table_rtl(self.clients_table)
        self.clients_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.clients_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.clients_table.setAlternatingRowColors(True)
        v_header = self.clients_table.verticalHeader()
        if v_header is not None:
            v_header.setDefaultSectionSize(50)
            v_header.setVisible(False)
        h_header = self.clients_table.horizontalHeader()
        if h_header is not None:
            # اللوجو ثابت، الاسم والشركة والإيميل يتمددون، الباقي بحجم المحتوى
            h_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)  # اللوجو
            self.clients_table.setColumnWidth(0, 60)  # ⚡ تصغير عرض العمود ليكون اللوجو في المنتصف
            h_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # الاسم - يتمدد
            h_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # الشركة - يتمدد
            h_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # الهاتف
            h_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)  # الإيميل - يتمدد
            h_header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)  # إجمالي المشاريع
            h_header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)  # إجمالي المدفوعات
            h_header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)  # الحالة
        self.clients_table.itemSelectionChanged.connect(self.on_client_selection_changed)

        # إضافة دبل كليك للتعديل
        self.clients_table.itemDoubleClicked.connect(self.open_editor_for_selected)
        
        # إضافة قائمة السياق (كليك يمين)
        self._setup_context_menu()

        table_layout.addWidget(self.clients_table)
        main_layout.addWidget(table_groupbox, 1)

        # ⚡ تحميل البيانات بعد ظهور النافذة (لتجنب التجميد)
        # self.load_clients_data() - يتم استدعاؤها من MainWindow
        self.update_buttons_state(False)

    def _setup_context_menu(self):
        """إعداد قائمة السياق (كليك يمين) للجدول"""
        from core.context_menu import ContextMenuManager
        
        ContextMenuManager.setup_table_context_menu(
            table=self.clients_table,
            on_view=self.open_editor_for_selected,
            on_edit=self.open_editor_for_selected,
            on_delete=self.delete_selected_client,
            on_refresh=self.load_clients_data,
            on_export=self.export_clients
        )

    def export_clients(self):
        """تصدير العملاء إلى Excel"""
        try:
            # الحصول على خدمة التصدير من النافذة الرئيسية
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'export_service'):
                main_window = main_window.parent()

            export_service = getattr(main_window, 'export_service', None) if main_window else None

            if not export_service:
                QMessageBox.warning(self, "خدمة التصدير غير متوفرة", "يرجى تثبيت pandas: pip install pandas openpyxl")
                return

            # تصدير العملاء
            filepath = export_service.export_clients_to_excel(self.clients_list)

            if filepath:
                reply = QMessageBox.question(
                    self,
                    "تم التصدير",
                    f"تم تصدير {len(self.clients_list)} عميل بنجاح إلى:\n{filepath}\n\nهل تريد فتح الملف؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.Yes:
                    export_service.open_file(filepath)
            else:
                QMessageBox.warning(self, "خطأ", "فشل في تصدير البيانات")

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في التصدير:\n{str(e)}")

    def import_clients(self):
        """استيراد العملاء من ملف Excel"""
        try:
            from PyQt6.QtWidgets import QFileDialog

            # الحصول على خدمة التصدير من النافذة الرئيسية
            main_window = self.parent()
            while main_window and not hasattr(main_window, 'export_service'):
                main_window = main_window.parent()

            export_service = getattr(main_window, 'export_service', None) if main_window else None

            if not export_service:
                QMessageBox.warning(self, "خدمة الاستيراد غير متوفرة", "يرجى تثبيت pandas: pip install pandas openpyxl")
                return

            # اختيار ملف Excel
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "اختر ملف Excel للاستيراد",
                "",
                "Excel Files (*.xlsx *.xls)"
            )

            if not filepath:
                return

            # استيراد البيانات
            clients_data, errors = export_service.import_clients_from_excel(filepath)

            if errors:
                error_msg = "\n".join(errors[:10])  # عرض أول 10 أخطاء
                if len(errors) > 10:
                    error_msg += f"\n... و {len(errors) - 10} خطأ آخر"

                reply = QMessageBox.question(
                    self,
                    "تحذير",
                    f"تم العثور على {len(errors)} خطأ:\n\n{error_msg}\n\nهل تريد المتابعة باستيراد البيانات الصحيحة ({len(clients_data)} عميل)؟",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )

                if reply == QMessageBox.StandardButton.No:
                    return

            if not clients_data:
                QMessageBox.warning(self, "لا توجد بيانات", "لم يتم العثور على بيانات صحيحة للاستيراد")
                return

            # استيراد العملاء
            success_count = 0
            failed_count = 0

            for client_dict in clients_data:
                try:
                    # إنشاء عميل جديد
                    client = schemas.Client(**client_dict)
                    self.client_service.create_client(client)
                    success_count += 1
                except Exception as e:
                    safe_print(f"ERROR: فشل استيراد عميل {client_dict.get('name')}: {e}")
                    failed_count += 1

            # تحديث الجدول
            self.load_clients_data()

            # عرض النتيجة
            result_msg = f"✅ تم استيراد {success_count} عميل بنجاح"
            if failed_count > 0:
                result_msg += f"\n❌ فشل استيراد {failed_count} عميل"

            QMessageBox.information(self, "نتيجة الاستيراد", result_msg)

        except Exception as e:
            QMessageBox.critical(self, "خطأ", f"فشل في الاستيراد:\n{str(e)}")

    def update_buttons_state(self, has_selection: bool):
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)

    def on_client_selection_changed(self):
        # ⚡ تجاهل التحديث إذا كان الكليك يمين
        from core.context_menu import is_right_click_active
        if is_right_click_active():
            return
        
        selected_rows = self.clients_table.selectedIndexes()
        if selected_rows:
            selected_index = selected_rows[0].row()
            if 0 <= selected_index < len(self.clients_list):
                self.selected_client = self.clients_list[selected_index]
                self.update_buttons_state(True)
                return
        self.selected_client = None
        self.update_buttons_state(False)

    def load_clients_data(self):
        """⚡ تحميل بيانات العملاء في الخلفية لمنع التجميد"""
        safe_print("INFO: [ClientManager] جاري تحميل بيانات العملاء...")

        from core.data_loader import get_data_loader

        # تحضير الجدول
        self.clients_table.setSortingEnabled(False)
        self.clients_table.setUpdatesEnabled(False)
        self.clients_table.blockSignals(True)
        self.clients_table.setRowCount(0)

        # دالة جلب البيانات (تعمل في الخلفية)
        def fetch_clients():
            try:
                # جلب العملاء
                if self.show_archived_checkbox.isChecked():
                    clients = self.client_service.get_archived_clients()
                else:
                    clients = self.client_service.get_all_clients()

                # جلب الإجماليات
                client_invoices_total = {}
                client_payments_total = {}

                try:
                    # ⚡ استخدام cursor منفصل لتجنب مشكلة Recursive cursor
                    cursor = self.client_service.repo.get_cursor()
                    try:
                        cursor.execute("""
                            SELECT client_id, SUM(total_amount) as total_projects
                            FROM projects
                            WHERE status != 'مؤرشف' AND status != 'ملغي'
                            GROUP BY client_id
                        """)
                        client_invoices_total = {str(row[0]): float(row[1]) if row[1] else 0.0
                                                for row in cursor.fetchall()}

                        cursor.execute("""
                            SELECT client_id, SUM(amount) as total_paid
                            FROM payments
                            WHERE client_id IS NOT NULL AND client_id != ''
                            GROUP BY client_id
                        """)
                        client_payments_total = {str(row[0]): float(row[1]) if row[1] else 0.0
                                                for row in cursor.fetchall()}
                    finally:
                        cursor.close()
                except Exception as e:
                    safe_print(f"ERROR: فشل حساب الإجماليات: {e}")

                return {
                    'clients': clients,
                    'invoices_total': client_invoices_total,
                    'payments_total': client_payments_total
                }
            except Exception as e:
                safe_print(f"ERROR: [ClientManager] فشل جلب العملاء: {e}")
                return {'clients': [], 'invoices_total': {}, 'payments_total': {}}

        # دالة تحديث الواجهة
        def on_data_loaded(data):
            try:
                self.clients_list = data['clients']
                client_invoices_total = data['invoices_total']
                client_payments_total = data['payments_total']

                self._populate_clients_table(client_invoices_total, client_payments_total)

            except Exception as e:
                safe_print(f"ERROR: [ClientManager] فشل تحديث الجدول: {e}")
                import traceback
                traceback.print_exc()
            finally:
                self.clients_table.blockSignals(False)
                self.clients_table.setUpdatesEnabled(True)
                self.clients_table.setSortingEnabled(True)

        def on_error(error_msg):
            safe_print(f"ERROR: [ClientManager] فشل تحميل العملاء: {error_msg}")
            self.clients_table.blockSignals(False)
            self.clients_table.setUpdatesEnabled(True)
            self.clients_table.setSortingEnabled(True)

        # تحميل البيانات في الخلفية
        data_loader = get_data_loader()
        data_loader.load_async(
            operation_name="clients_list",
            load_function=fetch_clients,
            on_success=on_data_loaded,
            on_error=on_error,
            use_thread_pool=True
        )

    def _populate_clients_table(self, client_invoices_total, client_payments_total):
        """ملء جدول العملاء بالبيانات - محسّن للسرعة مع تمييز VIP"""

        # ⚡ تحميل البيانات على دفعات أكبر للسرعة
        batch_size = 25
        total_clients = len(self.clients_list)
        
        # ⚡ تعيين عدد الصفوف مرة واحدة (أسرع من insertRow)
        self.clients_table.setRowCount(total_clients)
        
        # ⚡ ألوان VIP الذهبية
        VIP_BG_COLOR = QColor("#2d2a1a")  # خلفية ذهبية داكنة
        VIP_TEXT_COLOR = QColor("#fbbf24")  # نص ذهبي
        VIP_BORDER_COLOR = QColor("#f59e0b")  # حدود ذهبية
        
        for index, client in enumerate(self.clients_list):
            # ⚡ التحقق من حالة VIP
            is_vip = getattr(client, 'is_vip', False)

            # ⚡ عرض لوجو العميل بشكل دائري احترافي - بدون مربع
            logo_container = QWidget()
            logo_container.setStyleSheet("""
                QWidget {
                    background: transparent;
                    border: none;
                    margin: 0;
                    padding: 0;
                }
            """)
            logo_layout = QHBoxLayout(logo_container)
            logo_layout.setContentsMargins(0, 0, 0, 0)
            logo_layout.setSpacing(0)
            logo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # إنشاء الـ label - في المنتصف تماماً
            logo_label = QLabel()
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setFixedSize(40, 40)
            logo_label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    border: none;
                    margin: 0;
                    padding: 0;
                }
            """)
            
            pixmap = None
            has_logo = False

            # محاولة تحميل الصورة من base64
            if hasattr(client, 'logo_data') and client.logo_data and client.logo_data.strip():
                try:
                    import base64
                    logo_data = client.logo_data.strip()
                    if logo_data.startswith('data:image'):
                        logo_data = logo_data.split(',')[1]
                    img_bytes = base64.b64decode(logo_data)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(img_bytes):
                        has_logo = True
                except:
                    pixmap = None

            # محاولة تحميل من المسار المحلي
            if not has_logo and hasattr(client, 'logo_path') and client.logo_path and os.path.exists(client.logo_path):
                try:
                    pixmap = QPixmap(client.logo_path)
                    if not pixmap.isNull():
                        has_logo = True
                except:
                    pixmap = None

            # عرض الصورة الدائرية
            if has_logo and pixmap and not pixmap.isNull():
                from PyQt6.QtGui import QPainter, QBrush, QPainterPath
                from PyQt6.QtCore import QRectF
                
                # تصغير الصورة
                size = 40
                scaled = pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                
                # قص لتكون مربعة
                if scaled.width() > size:
                    x = (scaled.width() - size) // 2
                    scaled = scaled.copy(x, 0, size, size)
                if scaled.height() > size:
                    y = (scaled.height() - size) // 2
                    scaled = scaled.copy(0, y, size, size)
                
                # إنشاء صورة دائرية
                circular = QPixmap(size, size)
                circular.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(circular)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                
                path = QPainterPath()
                path.addEllipse(QRectF(0, 0, size, size))
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, scaled)
                
                # ⚡ إضافة حدود ذهبية لـ VIP
                if is_vip:
                    from PyQt6.QtGui import QPen
                    painter.setClipping(False)
                    pen = QPen(VIP_BORDER_COLOR, 3)
                    painter.setPen(pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawEllipse(1, 1, size-2, size-2)
                
                painter.end()
                
                logo_label.setPixmap(circular)
            else:
                # أيقونة افتراضية - دائرة ملونة مع الحرف الأول
                first_char = (client.name[0] if client.name else "?")
                
                # ⚡ لون ذهبي لـ VIP
                if is_vip:
                    bg = "#f59e0b"  # ذهبي
                else:
                    colors = ["#3B82F6", "#10B981", "#8B5CF6", "#F59E0B", "#EF4444", "#EC4899", "#06B6D4"]
                    color_idx = sum(ord(c) for c in (client.name or "A")) % len(colors)
                    bg = colors[color_idx]
                
                # رسم الدائرة مع الحرف
                from PyQt6.QtGui import QPainter, QFont, QPen
                from PyQt6.QtCore import QRectF
                
                size = 40
                avatar = QPixmap(size, size)
                avatar.fill(Qt.GlobalColor.transparent)
                
                painter = QPainter(avatar)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
                
                # رسم الدائرة الملونة
                painter.setBrush(QColor(bg))
                painter.setPen(QPen(Qt.GlobalColor.transparent))
                painter.drawEllipse(0, 0, size, size)
                
                # رسم الحرف
                painter.setPen(QPen(QColor("white")))
                font = QFont("Cairo", 16, QFont.Weight.Bold)
                painter.setFont(font)
                painter.drawText(QRectF(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, first_char)
                painter.end()
                
                logo_label.setPixmap(avatar)

            logo_layout.addWidget(logo_label)
            
            # ⚡ إضافة item فارغ للتحكم في الـ background
            empty_item = QTableWidgetItem()
            if is_vip:
                empty_item.setBackground(VIP_BG_COLOR)
            else:
                empty_item.setBackground(QColor("transparent"))
            self.clients_table.setItem(index, 0, empty_item)
            self.clients_table.setCellWidget(index, 0, logo_container)

            # ⚡ الاسم مع علامة VIP
            name_text = f"⭐ {client.name}" if is_vip else (client.name or "")
            name_item = create_centered_item(name_text)
            if is_vip:
                name_item.setForeground(VIP_TEXT_COLOR)
                name_item.setFont(get_cairo_font(11, bold=True))
                name_item.setBackground(VIP_BG_COLOR)
            self.clients_table.setItem(index, 1, name_item)
            
            # ⚡ باقي الأعمدة مع تلوين VIP
            company_item = create_centered_item(client.company_name or "")
            phone_item = create_centered_item(client.phone or "")
            email_item = create_centered_item(client.email or "")
            
            if is_vip:
                company_item.setBackground(VIP_BG_COLOR)
                phone_item.setBackground(VIP_BG_COLOR)
                email_item.setBackground(VIP_BG_COLOR)
            
            self.clients_table.setItem(index, 2, company_item)
            self.clients_table.setItem(index, 3, phone_item)
            self.clients_table.setItem(index, 4, email_item)

            # جلب إجماليات العميل
            client_name = client.name
            total_invoices = client_invoices_total.get(client_name, 0.0)
            total_payments = client_payments_total.get(client_name, 0.0)

            # عرض إجمالي الفواتير
            total_item = create_centered_item(f"{total_invoices:,.0f} ج.م")
            total_item.setData(Qt.ItemDataRole.UserRole, total_invoices)
            total_item.setForeground(QColor("#2454a5"))
            total_item.setFont(get_cairo_font(10, bold=True))
            if is_vip:
                total_item.setBackground(VIP_BG_COLOR)
            self.clients_table.setItem(index, 5, total_item)

            # عرض إجمالي المدفوعات
            payment_item = create_centered_item(f"{total_payments:,.0f} ج.م")
            payment_item.setData(Qt.ItemDataRole.UserRole, total_payments)
            payment_item.setForeground(QColor("#00a876"))
            payment_item.setFont(get_cairo_font(10, bold=True))
            if is_vip:
                payment_item.setBackground(VIP_BG_COLOR)
            self.clients_table.setItem(index, 6, payment_item)

            # الحالة مع لون الخلفية
            if is_vip:
                # ⚡ VIP يظهر بلون ذهبي
                status_item = create_centered_item("⭐ VIP")
                status_item.setBackground(QColor("#f59e0b"))
                status_item.setForeground(QColor("white"))
                status_item.setFont(get_cairo_font(10, bold=True))
            else:
                bg_color = QColor("#ef4444") if client.status == schemas.ClientStatus.ARCHIVED else QColor("#0A6CF1")
                status_item = create_centered_item(client.status.value, bg_color)
                status_item.setForeground(QColor("white"))
            self.clients_table.setItem(index, 7, status_item)

        safe_print(f"INFO: [ClientManager] ✅ تم تحميل {len(self.clients_list)} عميل.")

        self.selected_client = None
        self.update_buttons_state(False)

    def _on_clients_changed(self):
        """⚡ استجابة لإشارة تحديث العملاء - تحديث الجدول أوتوماتيك"""
        safe_print("INFO: [ClientManager] ⚡ استلام إشارة تحديث العملاء - جاري التحديث...")
        # ⚡ إبطال الـ cache لضمان جلب البيانات الجديدة (بما فيها الصور)
        self.client_service.invalidate_cache()
        self.load_clients_data()

    def open_editor(self, client_to_edit: schemas.Client | None):
        dialog = ClientEditorDialog(
            client_service=self.client_service,
            client_to_edit=client_to_edit,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.load_clients_data()

    def open_editor_for_selected(self):
        if not self.selected_client:
            QMessageBox.warning(self, "تحذير", "يرجى تحديد عميل من الجدول أولاً.")
            return
        self.open_editor(self.selected_client)

    def delete_selected_client(self):
        """حذف العميل المحدد بشكل احترافي"""
        if not self.selected_client:
            QMessageBox.warning(self, "تحذير", "يرجى اختيار عميل للحذف")
            return

        # رسالة تأكيد احترافية
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("⚠️ تأكيد الحذف")
        msg.setText(f"هل أنت متأكد من حذف العميل؟")
        msg.setInformativeText(
            f"العميل: {self.selected_client.name}\n"
            f"الشركة: {self.selected_client.company_name or 'غير محدد'}\n\n"
            f"⚠️ تحذير: هذا الإجراء لا يمكن التراجع عنه!"
        )
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        
        # تخصيص الأزرار
        yes_button = msg.button(QMessageBox.StandardButton.Yes)
        yes_button.setText("نعم، احذف")
        no_button = msg.button(QMessageBox.StandardButton.No)
        no_button.setText("إلغاء")

        reply = msg.exec()

        if reply == QMessageBox.StandardButton.Yes:
            try:
                # ⚡ استخدام المعرف الصحيح (_mongo_id أو id)
                client_id = getattr(self.selected_client, '_mongo_id', None) or str(self.selected_client.id)
                safe_print(f"DEBUG: [delete_selected_client] حذف العميل: {self.selected_client.name}")
                safe_print(f"DEBUG: [delete_selected_client] _mongo_id: {getattr(self.selected_client, '_mongo_id', None)}")
                safe_print(f"DEBUG: [delete_selected_client] id: {self.selected_client.id}")
                safe_print(f"DEBUG: [delete_selected_client] client_id المستخدم: {client_id}")
                
                result = self.client_service.delete_client(client_id)
                safe_print(f"DEBUG: [delete_selected_client] نتيجة الحذف: {result}")
                
                # رسالة نجاح
                QMessageBox.information(
                    self,
                    "✅ تم الحذف",
                    f"تم حذف العميل '{self.selected_client.name}' بنجاح"
                )
                
                # تحديث الجدول
                self.selected_client = None
                self.load_clients_data()
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "❌ خطأ",
                    f"فشل حذف العميل:\n{str(e)}"
                )
