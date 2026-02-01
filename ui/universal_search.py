"""
Universal Search Widget - Reusable search bar for all tables
"""

from PyQt6.QtWidgets import QLineEdit, QTableWidget


class UniversalSearchBar(QLineEdit):
    """
    Universal search bar that can filter any QTableWidget in real-time
    """

    def __init__(self, table: QTableWidget, placeholder: str = "بحث...", parent=None):
        super().__init__(parent)
        self.table = table
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)

        # Apply styling
        self.setStyleSheet(
            """
            QLineEdit {
                padding: 8px 12px;
                font-size: 14px;
                border: 2px solid #374151;
                border-radius: 6px;
                background-color: #1A202C;
                color: #F8FAFC;
            }
            QLineEdit:focus {
                border-color: #0A6CF1;
                outline: none;
            }
            QLineEdit::placeholder {
                color: #6B7280;
            }
        """
        )

        # Connect search signal
        self.textChanged.connect(self.filter_table)

    def filter_table(self, search_text: str):
        """
        Filter table rows based on search text (case-insensitive, searches all columns)
        """
        search_text = search_text.strip().lower()

        # If search is empty, show all rows
        if not search_text:
            for row in range(self.table.rowCount()):
                self.table.setRowHidden(row, False)
            return

        # Filter rows
        for row in range(self.table.rowCount()):
            match_found = False

            # Search across all columns
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item:
                    cell_text = item.text().lower()
                    if search_text in cell_text:
                        match_found = True
                        break

            # Hide row if no match found
            self.table.setRowHidden(row, not match_found)
