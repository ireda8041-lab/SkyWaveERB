#!/usr/bin/env python3
"""
فحص مشاكل قاعدة البيانات
"""

import sqlite3
import sys

def check_database():
    """فحص قاعدة البيانات"""
    print('🔍 فحص قاعدة البيانات...')
    
    conn = sqlite3.connect('skywave_local.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # فحص الدفعات
    cursor.execute('SELECT COUNT(*) FROM payments')
    payments_count = cursor.fetchone()[0]
    print(f'💰 الدفعات: {payments_count}')
    
    if payments_count > 0:
        cursor.execute('SELECT * FROM payments LIMIT 3')
        payments = cursor.fetchall()
        for payment in payments:
            print(f'  - دفعة: {payment["amount"]} - مشروع: {payment["project_id"]}')
    
    # فحص المصروفات
    cursor.execute('SELECT COUNT(*) FROM expenses')
    expenses_count = cursor.fetchone()[0]
    print(f'💸 المصروفات: {expenses_count}')
    
    if expenses_count > 0:
        cursor.execute('SELECT * FROM expenses LIMIT 3')
        expenses = cursor.fetchall()
        for expense in expenses:
            print(f'  - مصروف: {expense["amount"]} - {expense["description"]}')
    
    # فحص المستخدمين
    cursor.execute('SELECT COUNT(*) FROM users')
    users_count = cursor.fetchone()[0]
    print(f'👥 المستخدمين: {users_count}')
    
    if users_count > 0:
        cursor.execute('SELECT username, role FROM users')
        users = cursor.fetchall()
        for user in users:
            print(f'  - {user["username"]} ({user["role"]})')
    
    # فحص المشاريع
    cursor.execute('SELECT COUNT(*) FROM projects')
    projects_count = cursor.fetchone()[0]
    print(f'📁 المشاريع: {projects_count}')
    
    if projects_count > 0:
        cursor.execute('SELECT id, name, client_id FROM projects LIMIT 3')
        projects = cursor.fetchall()
        for project in projects:
            print(f'  - مشروع: {project["name"]} (ID: {project["id"]})')
    
    # فحص العملاء
    cursor.execute('SELECT COUNT(*) FROM clients')
    clients_count = cursor.fetchone()[0]
    print(f'👤 العملاء: {clients_count}')
    
    conn.close()
    
    return {
        'payments': payments_count,
        'expenses': expenses_count,
        'users': users_count,
        'projects': projects_count,
        'clients': clients_count
    }

if __name__ == "__main__":
    results = check_database()
    print(f"\n📊 ملخص: {results}")