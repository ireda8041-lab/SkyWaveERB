"""
اختبار عرض الدفعات في الجدول
"""
import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

def test_table():
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("اختبار جدول الدفعات")
    window.setGeometry(100, 100, 600, 400)
    
    # إنشاء الجدول
    table = QTableWidget()
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["الحساب", "المبلغ", "التاريخ"])
    
    # إضافة بيانات تجريبية
    test_data = [
        ("V/F HAZEM", 5000.00, "2025-01-15"),
        ("نقدي", 3000.00, "2025-01-10"),
        ("بنك مصر", 7500.50, "2025-01-05"),
    ]
    
    table.setRowCount(len(test_data))
    
    for i, (account, amount, date) in enumerate(test_data):
        # عمود 0: الحساب
        account_item = QTableWidgetItem(account)
        account_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(i, 0, account_item)
        print(f"صف {i}, عمود 0: {account}")
        
        # عمود 1: المبلغ
        amount_item = QTableWidgetItem(f"{amount:,.2f} ج.م")
        amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        amount_item.setForeground(QColor("#10b981"))
        table.setItem(i, 1, amount_item)
        print(f"صف {i}, عمود 1: {amount:,.2f} ج.م")
        
        # عمود 2: التاريخ
        date_item = QTableWidgetItem(date)
        date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        table.setItem(i, 2, date_item)
        print(f"صف {i}, عمود 2: {date}")
    
    # التحقق من البيانات
    print("\n=== التحقق من البيانات في الجدول ===")
    for row in range(table.rowCount()):
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                print(f"صف {row}, عمود {col}: {item.text()}")
            else:
                print(f"صف {row}, عمود {col}: فارغ!")
    
    # عرض الجدول
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    layout.addWidget(table)
    window.setCentralWidget(central_widget)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    test_table()
