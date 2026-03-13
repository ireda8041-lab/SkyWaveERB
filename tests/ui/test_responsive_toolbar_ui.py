from PyQt6.QtWidgets import QPushButton


def test_responsive_toolbar_normalizes_compact_button_height(qapp):
    from ui.responsive_toolbar import ResponsiveToolbar

    toolbar = ResponsiveToolbar()
    try:
        button = QPushButton("🔄 تحديث")
        button.setFixedHeight(28)

        toolbar.addButton(button)

        assert toolbar.objectName() == "ResponsiveToolbar"
        assert button.height() >= 32
        assert "QWidget#ResponsiveToolbar QPushButton" in toolbar.styleSheet()
    finally:
        toolbar.close()
