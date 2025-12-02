"""
Quick test for Universal Search functionality
Run this to verify the search bar works correctly
"""
import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QTableWidget, QTableWidgetItem
from ui.universal_search import UniversalSearchBar


def test_search():
    app = QApplication(sys.argv)
    
    # Create test window
    window = QWidget()
    window.setWindowTitle("Universal Search Test")
    window.resize(800, 600)
    layout = QVBoxLayout()
    
    # Create test table
    table = QTableWidget()
    table.setColumnCount(4)
    table.setHorizontalHeaderLabels(["Name", "Company", "Phone", "Email"])
    
    # Add test data
    test_data = [
        ["محمد أحمد", "Sky Wave", "01012345678", "mohamed@example.com"],
        ["أحمد علي", "Tech Corp", "01098765432", "ahmed@example.com"],
        ["فاطمة حسن", "Digital Agency", "01055555555", "fatima@example.com"],
        ["علي محمود", "Sky Wave", "01066666666", "ali@example.com"],
        ["سارة إبراهيم", "Marketing Pro", "01077777777", "sara@example.com"],
    ]
    
    table.setRowCount(len(test_data))
    for row, data in enumerate(test_data):
        for col, value in enumerate(data):
            table.setItem(row, col, QTableWidgetItem(value))
    
    # Add search bar
    search_bar = UniversalSearchBar(
        table,
        placeholder="🔍 Search (Name, Company, Phone, Email)..."
    )
    
    layout.addWidget(search_bar)
    layout.addWidget(table)
    window.setLayout(layout)
    
    window.show()
    
    print("✅ Universal Search Test Window Opened")
    print("📝 Try searching for:")
    print("   - 'محمد' (should show 2 rows)")
    print("   - 'Sky Wave' (should show 2 rows)")
    print("   - '0101' (should show 1 row)")
    print("   - 'example.com' (should show all 5 rows)")
    
    sys.exit(app.exec())


if __name__ == "__main__":
    test_search()
