#!/usr/bin/env python3
"""
اختبار سريع للتحديثات الفورية
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

def test_signals():
    """اختبار الإشارات"""
    print("=" * 60)
    print("اختبار نظام الإشارات")
    print("=" * 60)
    
    try:
        from core.signals import app_signals
        from core.repository import Repository
        
        print("✅ تم استيراد app_signals و Repository")
        
        # اختبار الإشارات
        signals_to_test = [
            'clients_changed',
            'projects_changed',
            'expenses_changed',
            'payments_changed',
            'services_changed',
            'accounting_changed'
        ]
        
        for signal_name in signals_to_test:
            if hasattr(app_signals, signal_name):
                print(f"✅ {signal_name} موجودة")
            else:
                print(f"❌ {signal_name} غير موجودة!")
        
        # اختبار Repository
        print("\nاختبار Repository:")
        if hasattr(Repository, 'data_changed_signal'):
            print("✅ Repository.data_changed_signal موجودة")
        else:
            print("❌ Repository.data_changed_signal غير موجودة!")
        
        # اختبار الاتصال
        print("\nاختبار الاتصال:")
        
        counter = {'count': 0}
        
        def on_clients_changed():
            counter['count'] += 1
            print(f"🔥 clients_changed تم استقبالها! (#{counter['count']})")
        
        app_signals.clients_changed.connect(on_clients_changed)
        print("✅ تم ربط clients_changed")
        
        # اختبار الإرسال
        print("\nاختبار الإرسال:")
        app_signals.emit_data_changed("clients")
        
        # انتظار قليل
        QTimer.singleShot(100, lambda: print(f"\n✅ تم استقبال {counter['count']} إشارة"))
        QTimer.singleShot(200, QApplication.quit)
        
        return True
        
    except Exception as e:
        print(f"❌ خطأ: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    print("\n🔥 بدء اختبار التحديثات الفورية\n")
    
    success = test_signals()
    
    if success:
        sys.exit(app.exec())
    else:
        sys.exit(1)
