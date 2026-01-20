"""
فحص مشكلة عرض الجداول - اختبار مباشر
"""
import sqlite3
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, 
                              QTableWidgetItem, QVBoxLayout, QWidget, QHeaderView)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

def test_expenses_table():
    """اختبار جدول المصروفات"""
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("اختبار جدول المصروفات")
    window.setGeometry(100, 100, 800, 600)
    
    # إنشاء الجدول بنفس الطريقة في البرنامج
    table = QTableWidget()
    table.setColumnCount(3)
    table.setHorizontalHeaderLabels(["المبلغ", "الوصف", "التاريخ"])
    
    # تطبيق نفس الـ resize modes
    header = table.horizontalHeader()
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
    
    # جلب بيانات حقيقية من قاعدة البيانات
    conn = sqlite3.connect('skywave_local.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # جلب أول 5 مصروفات
    cursor.execute("SELECT * FROM expenses LIMIT 5")
    expenses = cursor.fetchall()
    
    print(f"عدد المصروفات: {len(expenses)}")
    
    if len(expenses) > 0:
        table.setRowCount(len(expenses))
        
        for i, exp in enumerate(expenses):
            print(f"\nمصروف #{i+1}:")
            print(f"  المبلغ: {exp['amount']}")
            desc_val = exp['description'] if 'description' in exp.keys() else 'N/A'
            print(f"  الوصف: {desc_val}")
            print(f"  التاريخ: {exp['date']}")
            
            # عمود 0: المبلغ
            amount_item = QTableWidgetItem(f"{exp['amount']:,.2f}")
            amount_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            amount_item.setForeground(QColor("#ef4444"))
            table.setItem(i, 0, amount_item)
            print(f"  -> تم وضع المبلغ في العمود 0")
            
            # عمود 1: الوصف
            desc = exp['description'] if 'description' in exp.keys() else (exp['category'] if 'category' in exp.keys() else "-")
            desc_item = QTableWidgetItem(str(desc))
            desc_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, desc_item)
            print(f"  -> تم وضع الوصف في العمود 1: {desc}")
            
            # عمود 2: التاريخ
            date_str = str(exp['date'])[:10]
            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 2, date_item)
            print(f"  -> تم وضع التاريخ في العمود 2: {date_str}")
    else:
        print("لا توجد مصروفات!")
        table.setRowCount(1)
        no_data_item = QTableWidgetItem("لا توجد مصروفات")
        table.setItem(0, 0, no_data_item)
        table.setSpan(0, 0, 1, 3)
    
    conn.close()
    
    # التحقق من البيانات في الجدول
    print("\n" + "="*80)
    print("التحقق من البيانات في الجدول:")
    print("="*80)
    for row in range(table.rowCount()):
        print(f"\nصف {row}:")
        for col in range(table.columnCount()):
            item = table.item(row, col)
            if item:
                print(f"  عمود {col}: '{item.text()}'")
                # فحص الـ span
                row_span = table.rowSpan(row, col)
                col_span = table.columnSpan(row, col)
                if row_span > 1 or col_span > 1:
                    print(f"    ⚠️ SPAN: {row_span}x{col_span}")
            else:
                print(f"  عمود {col}: فارغ")
    
    # عرض الجدول
    central_widget = QWidget()
    layout = QVBoxLayout(central_widget)
    layout.addWidget(table)
    window.setCentralWidget(central_widget)
    
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    test_expenses_table()
