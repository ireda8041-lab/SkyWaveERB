#!/usr/bin/env python3
"""
Test script to verify the sync refactoring implementation
Run this to check if all components are properly configured
"""

import json
import sys
from pathlib import Path


def test_sync_config():
    """Test sync_config.json has correct intervals"""
    print("=" * 60)
    print("Testing sync_config.json...")
    print("=" * 60)
    
    config_path = Path("sync_config.json")
    if not config_path.exists():
        print("❌ FAIL: sync_config.json not found")
        return False
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    checks = {
        "auto_sync_interval": (300, "Should be 300 seconds (5 minutes)"),
        "quick_sync_interval": (300, "Should be 300 seconds (5 minutes)"),
        "connection_check_interval": (30, "Should be 30 seconds"),
    }
    
    all_passed = True
    for key, (expected, description) in checks.items():
        actual = config.get(key)
        if actual == expected:
            print(f"✅ {key}: {actual}s - {description}")
        else:
            print(f"❌ {key}: {actual}s (expected {expected}s) - {description}")
            all_passed = False
    
    return all_passed


def test_repository_signals():
    """Test that Repository has data_changed_signal"""
    print("\n" + "=" * 60)
    print("Testing Repository signals...")
    print("=" * 60)
    
    try:
        from core.repository import Repository
        from PyQt6.QtCore import QObject
        
        # Check if Repository inherits from QObject
        if not issubclass(Repository, QObject):
            print("❌ FAIL: Repository does not inherit from QObject")
            return False
        print("✅ Repository inherits from QObject")
        
        # Check if data_changed_signal exists
        if not hasattr(Repository, 'data_changed_signal'):
            print("❌ FAIL: Repository does not have data_changed_signal")
            return False
        print("✅ Repository has data_changed_signal")
        
        return True
        
    except Exception as e:
        print(f"❌ FAIL: Error testing Repository: {e}")
        return False


def test_signal_emissions():
    """Test that critical methods emit signals"""
    print("\n" + "=" * 60)
    print("Testing signal emissions in repository.py...")
    print("=" * 60)
    
    repo_path = Path("core/repository.py")
    if not repo_path.exists():
        print("❌ FAIL: core/repository.py not found")
        return False
    
    with open(repo_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for signal emissions in critical methods
    methods_to_check = [
        ("create_client", "clients"),
        ("update_client", "clients"),
        ("create_project", "projects"),
        ("update_project", "projects"),
        ("delete_project", "projects"),
        ("create_expense", "expenses"),
        ("update_expense", "expenses"),
        ("create_payment", "payments"),
        ("create_service", "services"),
        ("update_service", "services"),
        ("update_account", "accounts"),
    ]
    
    all_passed = True
    for method_name, table_name in methods_to_check:
        # Look for the method definition
        if f"def {method_name}(" in content:
            # Check if it emits the signal
            method_start = content.find(f"def {method_name}(")
            # Find the next method definition or end of file
            next_method = content.find("\n    def ", method_start + 1)
            if next_method == -1:
                next_method = len(content)
            
            method_content = content[method_start:next_method]
            
            if f'data_changed_signal.emit("{table_name}")' in method_content:
                print(f"✅ {method_name}() emits signal for '{table_name}'")
            else:
                print(f"❌ {method_name}() does NOT emit signal for '{table_name}'")
                all_passed = False
        else:
            print(f"⚠️  {method_name}() not found in repository.py")
    
    return all_passed


def test_signals_throttling():
    """Test that signals.py has proper throttling"""
    print("\n" + "=" * 60)
    print("Testing signals.py throttling...")
    print("=" * 60)
    
    signals_path = Path("core/signals.py")
    if not signals_path.exists():
        print("❌ FAIL: core/signals.py not found")
        return False
    
    with open(signals_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for throttling configuration
    if "_sync_throttle_seconds = 2.0" in content:
        print("✅ Throttling set to 2.0 seconds (reasonable)")
        return True
    elif "_sync_throttle_seconds = 0.1" in content:
        print("❌ FAIL: Throttling still at 0.1 seconds (too aggressive)")
        return False
    else:
        print("⚠️  WARNING: Could not find _sync_throttle_seconds setting")
        return False


def test_main_connections():
    """Test that main.py has proper signal connections"""
    print("\n" + "=" * 60)
    print("Testing main.py signal connections...")
    print("=" * 60)
    
    main_path = Path("main.py")
    if not main_path.exists():
        print("❌ FAIL: main.py not found")
        return False
    
    with open(main_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    checks = [
        ("self.repository.data_changed_signal.connect(app_signals.emit_data_changed)", 
         "Repository signal connected to app_signals"),
        ("app_signals.set_sync_manager(self.unified_sync)", 
         "Sync manager set in app_signals"),
    ]
    
    all_passed = True
    for check_str, description in checks:
        if check_str in content:
            print(f"✅ {description}")
        else:
            print(f"❌ FAIL: {description} - NOT FOUND")
            all_passed = False
    
    return all_passed


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("SYNC REFACTORING VERIFICATION TEST")
    print("=" * 60)
    
    tests = [
        ("Sync Configuration", test_sync_config),
        ("Repository Signals", test_repository_signals),
        ("Signal Emissions", test_signal_emissions),
        ("Signals Throttling", test_signals_throttling),
        ("Main Connections", test_main_connections),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ ERROR in {test_name}: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed")
    print("=" * 60)
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED! Sync refactoring is complete.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
