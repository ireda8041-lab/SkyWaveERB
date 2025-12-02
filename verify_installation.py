#!/usr/bin/env python3
"""
Installation Verification Script
Checks if all required libraries are properly installed
"""

import sys
import importlib

def check_library(name, import_name=None):
    """Check if a library is installed and importable"""
    if import_name is None:
        import_name = name
    
    try:
        lib = importlib.import_module(import_name)
        version = getattr(lib, '__version__', 'Unknown')
        print(f"✅ {name}: {version}")
        return True
    except ImportError as e:
        print(f"❌ {name}: NOT INSTALLED - {e}")
        return False

def main():
    print("=" * 60)
    print("🔍 Sky Wave ERP - Installation Verification")
    print("=" * 60)
    
    # Core libraries for new architecture
    libraries = [
        # GUI Framework
        ("PyQt6", "PyQt6.QtCore"),
        
        # Database
        ("pymongo", "pymongo"),
        
        # Smart Invoice Manager (Chrome-Only Strategy)
        ("selenium", "selenium"),
        ("webdriver-manager", "webdriver_manager"),
        
        # Template Engine
        ("Jinja2", "jinja2"),
        
        # PDF & Document Processing
        ("reportlab", "reportlab"),
        ("arabic-reshaper", "arabic_reshaper"),
        ("python-bidi", "bidi"),
        ("Pillow", "PIL"),
        
        # Data Export
        ("pandas", "pandas"),
        ("openpyxl", "openpyxl"),
        
        # Utilities
        ("python-dateutil", "dateutil"),
        ("requests", "requests"),
        
        # Logging
        ("colorlog", "colorlog"),
        
        # Validation
        ("pydantic", "pydantic"),
    ]
    
    print("\n📦 Checking Core Libraries:")
    print("-" * 40)
    
    success_count = 0
    total_count = len(libraries)
    
    for name, import_name in libraries:
        if check_library(name, import_name):
            success_count += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Installation Summary: {success_count}/{total_count} libraries installed")
    
    if success_count == total_count:
        print("🎉 ALL LIBRARIES INSTALLED SUCCESSFULLY!")
        print("✅ Sky Wave ERP is ready to run with the new architecture")
        
        # Test Smart Invoice Manager specifically
        print("\n🧪 Testing Smart Invoice Manager...")
        try:
            from services.smart_invoice_manager import SmartInvoiceManager
            print("✅ SmartInvoiceManager imported successfully")
            
            # Test Chrome driver availability
            try:
                from selenium import webdriver
                from webdriver_manager.chrome import ChromeDriverManager
                print("✅ Chrome WebDriver components available")
            except Exception as e:
                print(f"⚠️  Chrome WebDriver warning: {e}")
                
        except Exception as e:
            print(f"❌ SmartInvoiceManager test failed: {e}")
        
        return True
    else:
        print("❌ SOME LIBRARIES ARE MISSING!")
        print("💡 Run: pip install -r requirements.txt")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)