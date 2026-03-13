from unittest.mock import MagicMock

from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QBoxLayout

from core import schemas
from ui.account_editor_dialog import AccountEditorDialog


def _sample_accounts() -> list[schemas.Account]:
    return [
        schemas.Account(
            name="الأصول",
            code="1000",
            type=schemas.AccountType.ASSET,
            is_group=True,
        ),
        schemas.Account(
            name="النقدية والخزائن",
            code="1110",
            type=schemas.AccountType.CASH,
            parent_code="1000",
            is_group=True,
        ),
        schemas.Account(
            name="الخزنة الرئيسية",
            code="111001",
            type=schemas.AccountType.CASH,
            parent_code="1110",
        ),
    ]


def test_account_editor_parent_combo_timers_are_safe_on_fast_close(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
    )
    dialog.show()
    qt_app.processEvents()

    assert dialog.parent_combo.count() >= 2

    dialog.parent_combo.setFocus()
    qt_app.processEvents()
    QTest.qWait(5)

    line_edit = dialog.parent_combo.lineEdit()
    assert line_edit is not None

    line_edit.setText("111")
    dialog.parent_combo._on_text_edited("111")
    dialog.parent_combo._show_popup_safe()
    qt_app.processEvents()

    dialog.close()
    dialog.deleteLater()
    qt_app.processEvents()
    QTest.qWait(250)
    qt_app.processEvents()


def test_account_editor_cash_only_mode_exposes_cashbox_language(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    assert "خزنة" in dialog.windowTitle()
    assert dialog.save_button.text() == "💾 حفظ الخزنة"
    assert dialog.active_checkbox.text() == "خزنة نشطة"
    assert dialog.type_combo.currentData() == schemas.AccountType.CASH
    assert not dialog.type_combo.isEnabled()
    assert dialog.parent_combo.count() == 2
    assert dialog.cashbox_preset_combo.currentData() == "manual"
    assert dialog.cashbox_preset_combo.count() == 7
    assert len(dialog.cashbox_preset_buttons) == 7
    assert dialog.cashbox_preset_buttons["manual"].isChecked() is True
    assert "اختر أحد القوالب" in dialog.cashbox_preset_hint_label.text()
    assert dialog.treasury_type_combo.currentText() == "محفظة إلكترونية"
    assert dialog.treasury_details_title_label.text() == "بيانات المحافظ والأرقام المستقبلة"
    assert "01067894321" in dialog.treasury_details_input.placeholderText()
    assert dialog.summary_readiness_value.text() == "ينقصها تعريف"
    assert dialog.print_context_badge.text() == "راجع اسم الطباعة"
    assert "محفظة إلكترونية" in dialog.invoice_preview_method_value.text()
    assert dialog.summary_status_value.text() == "نشطة"
    assert dialog.balance_spinbox.isEnabled() is True

    dialog.close()


def test_account_editor_cash_preset_applies_operational_defaults(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    preset_index = dialog.cashbox_preset_combo.findData("bank_misr_local")
    dialog.cashbox_preset_combo.setCurrentIndex(preset_index)
    qt_app.processEvents()

    data = dialog.get_form_data()
    assert dialog.code_input.text() == "111004"
    assert dialog.name_input.text() == "Bank Misr Local"
    assert dialog.treasury_type_combo.currentText() == "تحويل بنكي داخل مصر"
    assert dialog.treasury_details_title_label.text() == "بيانات الحساب المحلي"
    assert "2630333000086626" in dialog.treasury_details_input.toPlainText()
    assert dialog.description_input.toPlainText() == "تحويل بنكي داخل مصر - بنك مصر"
    assert dialog.summary_name_value.text() == "Bank Misr Local"
    assert dialog.summary_invoice_value.text() == "Bank Misr Local"
    assert dialog.cashbox_preset_combo.currentData() == "bank_misr_local"
    assert dialog.cashbox_preset_buttons["bank_misr_local"].isChecked() is True
    assert "111004" in dialog.cashbox_preset_hint_label.text()
    assert dialog.invoice_preview_name_value.text() == "Bank Misr Local"
    assert "طريقة الدفع: تحويل بنكي داخل مصر" == dialog.invoice_preview_method_value.text()
    assert "نوع الخزنة: تحويل بنكي داخل مصر" in data["description"]
    assert "SWIFT CODE: BMISEGCXXXX" in data["description"]

    dialog.close()


def test_account_editor_cash_payment_preset_applies_cashbox_defaults(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    preset_index = dialog.cashbox_preset_combo.findData("cash_payment")
    dialog.cashbox_preset_combo.setCurrentIndex(preset_index)
    qt_app.processEvents()

    data = dialog.get_form_data()
    assert dialog.code_input.text() == "111006"
    assert dialog.name_input.text() == "Cash"
    assert dialog.treasury_type_combo.currentText() == "خزنة نقدية"
    assert dialog.treasury_details_title_label.text() == "موقع التحصيل والمسؤول المباشر"
    assert "الخزنة النقدية" in dialog.treasury_details_input.toPlainText()
    assert dialog.description_input.toPlainText() == "تحصيل نقدي مباشر داخل مقر الشركة"
    assert dialog.cashbox_preset_combo.currentData() == "cash_payment"
    assert dialog.cashbox_preset_buttons["cash_payment"].isChecked() is True
    assert "111006" in dialog.cashbox_preset_hint_label.text()
    assert dialog.invoice_preview_name_value.text() == "Cash"
    assert "نوع الخزنة: خزنة نقدية" in data["description"]

    dialog.close()


def test_account_editor_cash_summary_tracks_live_treasury_inputs(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    dialog.code_input.setText("111301")
    dialog.name_input.setText("VF Cash - Branch")
    dialog.treasury_type_combo.setCurrentText("محفظة إلكترونية")
    dialog.treasury_details_input.setPlainText("01067894321 - حازم أشرف\n01021965200 - رضا سامي")
    dialog.currency_combo.setCurrentIndex(1)
    dialog.balance_spinbox.setValue(2750.5)
    dialog.active_checkbox.setChecked(False)
    dialog.description_input.setText("تُستخدم للتحصيل اليومي فقط.")
    qt_app.processEvents()

    data = dialog.get_form_data()
    assert dialog.summary_code_value.text() == "111301"
    assert dialog.summary_name_value.text() == "VF Cash - Branch"
    assert dialog.summary_channel_value.text() == "محفظة إلكترونية"
    assert dialog.summary_readiness_value.text() == "جاهزة"
    assert dialog.summary_invoice_value.text() == "VF Cash - Branch"
    assert "USD" in dialog.summary_currency_value.text()
    assert "$" in dialog.summary_balance_value.text()
    assert dialog.summary_status_value.text() == "معطلة"
    assert dialog.summary_reference_value.text() == "01067894321 - حازم أشرف"
    assert "01067894321 - حازم أشرف" in dialog.summary_details_value.text()
    assert "للتحصيل اليومي" in dialog.summary_description_value.text()
    assert dialog.print_context_badge.text() == "طباعة جاهزة"
    assert "01067894321 - حازم أشرف" in dialog.invoice_preview_details_value.text()
    assert "نوع الخزنة: محفظة إلكترونية" in data["description"]
    assert "بيانات الخزنة:" in data["description"]
    assert "01021965200 - رضا سامي" in data["description"]

    dialog.close()


def test_account_editor_edit_mode_locks_balance_and_adapts_layout(qt_app):
    account = schemas.Account(
        name="V/F HAZEM",
        code="111301",
        type=schemas.AccountType.CASH,
        parent_code="1110",
        balance=44700.0,
        currency=schemas.CurrencyCode.EGP,
        description=(
            "نوع الخزنة: تحويل بنكي داخل مصر\n\n"
            "بيانات الخزنة:\nرقم الحساب: 2630333000086626\nSWIFT CODE: BMISEGCXXXX\n\n"
            "ملاحظات تشغيلية:\nيستخدم للتحويلات المحلية فقط."
        ),
        status=schemas.AccountStatus.ACTIVE,
    )
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        account_to_edit=account,
        cash_only=True,
    )
    dialog.resize(760, 680)
    dialog.show()
    qt_app.processEvents()

    assert dialog.save_button.text() == "💾 حفظ تعديل الخزنة"
    assert dialog.balance_spinbox.isEnabled() is False
    assert "حركة مالية" in dialog.balance_hint_label.text()
    assert dialog.balance_policy_badge.text() == "الرصيد يُدار بالحركة"
    assert dialog.cashbox_preset_combo.currentData() == "manual"
    assert dialog.treasury_type_combo.currentText() == "تحويل بنكي داخل مصر"
    assert "2630333000086626" in dialog.treasury_details_input.toPlainText()
    assert "للتحويلات المحلية" in dialog.description_input.toPlainText()

    dialog.resize(820, 680)
    qt_app.processEvents()
    assert dialog.body_layout.direction() == QBoxLayout.Direction.TopToBottom

    dialog.resize(1040, 680)
    qt_app.processEvents()
    assert dialog.body_layout.direction() == QBoxLayout.Direction.LeftToRight

    dialog.close()


def test_account_editor_edit_mode_detects_matching_operational_preset(qt_app):
    account = schemas.Account(
        name="Bank Misr Intl",
        code="111005",
        type=schemas.AccountType.CASH,
        parent_code="1110",
        balance=0.0,
        currency=schemas.CurrencyCode.EGP,
        description=(
            "نوع الخزنة: تحويل بنكي دولي\n\n"
            "بيانات الخزنة:\nIBAN: EG020002026302630333000086626\nSWIFT CODE: BMISEGCXXXX\n\n"
            "ملاحظات تشغيلية:\nتحويل بنكي من خارج مصر - بنك مصر"
        ),
        status=schemas.AccountStatus.ACTIVE,
    )
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        account_to_edit=account,
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    assert dialog.cashbox_preset_combo.currentData() == "bank_misr_international"
    assert "111005" in dialog.cashbox_preset_hint_label.text()
    assert dialog.treasury_type_combo.currentText() == "تحويل بنكي دولي"
    assert "EG020002026302630333000086626" in dialog.treasury_details_input.toPlainText()

    dialog.close()


def test_account_editor_preset_cards_drive_combo_selection(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    dialog.cashbox_preset_buttons["instapay"].click()
    qt_app.processEvents()

    assert dialog.cashbox_preset_combo.currentData() == "instapay"
    assert dialog.name_input.text() == "InstaPay"
    assert dialog.cashbox_preset_buttons["instapay"].isChecked() is True
    assert "InstaPay" in dialog.selected_preset_caption.text()

    dialog.close()


def test_account_editor_keyboard_shortcuts_support_select_copy_and_paste(qt_app):
    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    clipboard = QApplication.clipboard()
    clipboard.clear()

    dialog.name_input.setFocus()
    dialog.name_input.setText("VF Cash - Reda")
    qt_app.processEvents()

    QTest.keyClick(dialog, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()
    assert dialog.name_input.selectedText() == "VF Cash - Reda"

    QTest.keyClick(dialog, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()
    assert clipboard.text() == "VF Cash - Reda"

    dialog.name_input.clear()
    qt_app.processEvents()
    QTest.keyClick(dialog, Qt.Key.Key_V, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()
    assert dialog.name_input.text() == "VF Cash - Reda"

    dialog.description_input.setFocus()
    dialog.description_input.setPlainText("يستخدم للتحصيل السريع")
    qt_app.processEvents()
    QTest.keyClick(dialog, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()
    assert dialog.description_input.textCursor().selectedText() == "يستخدم للتحصيل السريع"

    dialog.close()


def test_account_editor_keyboard_shortcuts_support_save_escape_and_presets(monkeypatch, qt_app):
    accounting_service = MagicMock()
    dialog = AccountEditorDialog(
        accounting_service=accounting_service,
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    monkeypatch.setattr(
        "ui.account_editor_dialog.QMessageBox.information", lambda *args, **kwargs: None
    )
    dialog.show()
    qt_app.processEvents()

    QTest.keyClick(dialog, Qt.Key.Key_3, Qt.KeyboardModifier.AltModifier)
    qt_app.processEvents()

    assert dialog.cashbox_preset_combo.currentData() == "instapay"
    assert dialog.name_input.text() == "InstaPay"

    QTest.keyClick(dialog, Qt.Key.Key_S, Qt.KeyboardModifier.ControlModifier)
    qt_app.processEvents()

    accounting_service.create_account.assert_called_once()
    assert dialog.result() == dialog.DialogCode.Accepted

    dialog = AccountEditorDialog(
        accounting_service=MagicMock(),
        all_accounts=_sample_accounts(),
        cash_only=True,
    )
    dialog.show()
    qt_app.processEvents()

    dialog.code_input.setFocus()
    QTest.keyClick(dialog, Qt.Key.Key_Tab)
    qt_app.processEvents()
    assert dialog.name_input.hasFocus() is True

    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    qt_app.processEvents()
    assert dialog.result() == dialog.DialogCode.Rejected
