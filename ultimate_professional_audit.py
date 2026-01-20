#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
فحص احترافي نهائي بأقصى دقة - Ultimate Professional Audit
أقصى مستوى من الاحترافية والدقة لاكتشاف أي أخطاء مخفية
"""

import sys
import os
import ast
import re
import sqlite3
import json
import traceback
import importlib.util
import subprocess
import time
import threading
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Set
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib

# تعيين الترميز للـ console
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

class UltimateProfessionalAuditor:
    """فاحص احترافي نهائي بأقصى دقة"""
    
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.info = []
        self.critical_issues = []
        self.project_root = Path.cwd()
        self.total_files_checked = 0
        self.total_lines_checked = 0
        self.start_time = time.time()
        
        # قوائم شاملة للفحص
        self.python_files = []
        self.config_files = []
        self.database_files = []
        
        # المجلدات الأساسية للمشروع
        self.core_folders = ['core', 'services', 'ui', 'tests']
        self.core_files = ['main.py', 'version.py']
        
        # المجلدات المراد تجاهلها
        self.ignore_folders = [
            'dist', 'build', '__pycache__', '.venv', '.git', 
            '.pytest_cache', 'installer_output', 'exports'
        ]
        
        # أنماط الأخطاء المحتملة (شاملة ودقيقة)
        self.error_patterns = {
            'database_bool_critical': [
                r'\bif\s+(?:self\.)?(?:repo|db|database|connection)(?:\s*[^=\s]|:)',
                r'\bif\s+not\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\band\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\bor\s+(?:self\.)?(?:repo|db|database|connection)\b',
                r'\bwhile\s+(?:self\.)?(?:repo|db|database|connection)\b',
            ],
            'encoding_issues': [
                r'^\ufeff',  # BOM
                r'[^\x00-\x7F].*coding.*',  # Non-ASCII in encoding line
                r'coding[:=]\s*([-\w.]+)',  # Encoding declaration
            ],
            'import_issues': [
                r'from\s+\.\s+import',  # Relative import issues
                r'import\s+[^.\s]+\.[^.\s]+\.[^.\s]+',  # Deep imports
                r'from\s+__future__\s+import.*',  # Future imports position
            ],
            'sql_injection_critical': [
                r'execute\s*\(\s*["\'].*%.*["\']',  # String formatting in SQL
                r'execute\s*\(\s*f["\']',  # f-strings in SQL
                r'\.format\s*\(.*\)\s*\)',  # .format() in SQL
            ],
            'memory_leaks': [
                r'while\s+True:(?!.*break)',  # Infinite loops without break
                r'for.*in.*:(?!.*break)(?!.*return)',  # Potential infinite iterations
            ],
            'exception_handling': [
                r'except\s*:',  # Bare except
                r'except\s+Exception\s*:',  # Too broad exception
                r'pass\s*$',  # Empty except blocks
            ],
            'security_issues': [
                r'\beval\s*\(',  # eval usage
                r'\bexec\s*\(',  # exec usage
                r'shell\s*=\s*True',  # Shell injection
                r'password\s*=\s*["\'][^"\']+["\']',  # Hardcoded passwords
            ],
            'performance_issues': [
                r'\.append\s*\(.*\)\s*$',  # List append in loops
                r'for.*in.*\.keys\(\)',  # Iterating over dict keys
                r'\+\s*=.*["\']',  # String concatenation in loops
            ],
            'code_quality': [
                r'print\s*\(',  # Print statements (should use logging)
                r'TODO|FIXME|HACK',  # Code comments indicating issues
                r'def\s+\w+\s*\(\s*\):.*pass',  # Empty functions
            ]
        }
        
    def log_error(self, message: str, file_path: str = None, line_no: int = None, severity: str = "ERROR", category: str = "GENERAL"):
        """تسجيل خطأ مع تفاصيل كاملة ومصنفة"""
        error = {
            "type": severity,
            "category": category,
            "message": message,
            "file": file_path,
            "line": line_no,
            "timestamp": time.time()
        }
        
        if severity == "CRITICAL":
            self.critical_issues.append(error)
            print(f"🚨 CRITICAL [{category}]: {message}" + (f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""))
        elif severity == "ERROR":
            self.errors.append(error)
            print(f"❌ ERROR [{category}]: {message}" + (f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""))
        elif severity == "WARNING":
            self.warnings.append(error)
            print(f"⚠️ WARNING [{category}]: {message}" + (f" في {file_path}:{line_no}" if file_path and line_no else f" في {file_path}" if file_path else ""))
        
    def log_info(self, message: str, category: str = "INFO"):
        """تسجيل معلومة"""
        info = {"type": "INFO", "category": category, "message": message, "timestamp": time.time()}
        self.info.append(info)
        print(f"ℹ️ INFO [{category}]: {message}")

    def discover_project_files(self):
        """اكتشاف جميع ملفات المشروع الأساسية"""
        print("\n🔍 اكتشاف ملفات المشروع الأساسية...")
        print("=" * 60)
        
        # ملفات Python الأساسية
        for file_name in self.core_files:
            file_path = self.project_root / file_name
            if file_path.exists():
                self.python_files.append(file_path)
        
        # ملفات Python في المجلدات الأساسية
        for folder in self.core_folders:
            folder_path = self.project_root / folder
            if folder_path.exists():
                for py_file in folder_path.rglob('*.py'):
                    if not any(ignore in str(py_file) for ignore in self.ignore_folders):
                        self.python_files.append(py_file)
        
        # ملفات الإعدادات
        config_extensions = ['.json', '.ini', '.cfg', '.conf', '.yaml', '.yml', '.toml', '.env']
        for ext in config_extensions:
            for config_file in self.project_root.rglob(f'*{ext}'):
                if not any(ignore in str(config_file) for ignore in self.ignore_folders):
                    self.config_files.append(config_file)
        
        # ملفات قاعدة البيانات
        db_extensions = ['.db', '.sqlite', '.sqlite3']
        for ext in db_extensions:
            for db_file in self.project_root.rglob(f'*{ext}'):
                if not any(ignore in str(db_file) for ignore in self.ignore_folders):
                    self.database_files.append(db_file)
        
        self.log_info(f"تم اكتشاف {len(self.python_files)} ملف Python", "DISCOVERY")
        self.log_info(f"تم اكتشاف {len(self.config_files)} ملف إعدادات", "DISCOVERY")
        self.log_info(f"تم اكتشاف {len(self.database_files)} ملف قاعدة بيانات", "DISCOVERY")

    def ultra_deep_syntax_analysis(self) -> bool:
        """تحليل فائق العمق لصحة بناء الجملة"""
        print("\n🔍 تحليل فائق العمق لصحة بناء الجملة...")
        print("=" * 60)
        
        syntax_errors = 0
        encoding_errors = 0
        pattern_errors = 0
        
        def analyze_file_deeply(py_file):
            local_errors = []
            local_lines = 0
            
            try:
                # فحص الترميز والمحتوى
                with open(py_file, 'rb') as f:
                    raw_content = f.read()
                
                # فحص BOM
                if raw_content.startswith(b'\xef\xbb\xbf'):
                    local_errors.append(("ENCODING", f"ملف يحتوي على BOM", 1))
                
                # فحص الترميز
                try:
                    content = raw_content.decode('utf-8')
                except UnicodeDecodeError as e:
                    local_errors.append(("ENCODING", f"خطأ في الترميز: {e}", 1))
                    return local_errors, 0
                
                lines = content.split('\n')
                local_lines = len(lines)
                
                # فحص بناء الجملة المتقدم
                try:
                    tree = ast.parse(content, filename=str(py_file))
                    
                    # تحليل AST عميق
                    for node in ast.walk(tree):
                        # فحص الاستيرادات
                        if isinstance(node, ast.ImportFrom):
                            if node.module and '..' in node.module:
                                local_errors.append(("IMPORT", f"استيراد نسبي مشكوك فيه: {node.module}", getattr(node, 'lineno', 0)))
                        
                        # فحص الدوال الفارغة
                        if isinstance(node, ast.FunctionDef):
                            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                                local_errors.append(("QUALITY", f"دالة فارغة: {node.name}", getattr(node, 'lineno', 0)))
                        
                        # فحص استخدام eval/exec
                        if isinstance(node, ast.Call):
                            if isinstance(node.func, ast.Name) and node.func.id in ['eval', 'exec']:
                                local_errors.append(("SECURITY", f"استخدام خطير لـ {node.func.id}", getattr(node, 'lineno', 0)))
                
                except SyntaxError as e:
                    local_errors.append(("SYNTAX", f"خطأ في بناء الجملة: {e}", e.lineno))
                
                # فحص الأنماط المشكلة بدقة عالية
                for i, line in enumerate(lines, 1):
                    line_stripped = line.strip()
                    
                    # تجاهل التعليقات والأسطر الفارغة
                    if not line_stripped or line_stripped.startswith('#'):
                        continue
                    
                    for pattern_type, patterns in self.error_patterns.items():
                        for pattern in patterns:
                            if re.search(pattern, line):
                                # فحص الاستثناءات المُصلحة
                                if pattern_type == 'database_bool_critical':
                                    if 'is not None' in line or 'is None' in line:
                                        continue
                                    if any(safe in line for safe in ['.is_online()', 'hasattr', 'getattr']):
                                        continue
                                
                                if pattern_type == 'security_issues':
                                    if 'eval' in pattern and '.exec()' in line:  # PyQt exec() is safe
                                        continue
                                    if 'password' in pattern and ('test' in line.lower() or 'example' in line.lower()):
                                        continue
                                
                                local_errors.append(("PATTERN", f"نمط مشكل ({pattern_type}): {line_stripped}", i))
                
            except Exception as e:
                local_errors.append(("CRITICAL", f"خطأ غير متوقع في تحليل {py_file}: {e}", 1))
            
            return local_errors, local_lines
        
        # تحليل متوازي للملفات
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_file = {executor.submit(analyze_file_deeply, py_file): py_file for py_file in self.python_files}
            
            for future in as_completed(future_to_file):
                py_file = future_to_file[future]
                try:
                    file_errors, file_lines = future.result()
                    self.total_lines_checked += file_lines
                    
                    for error_type, error_msg, line_no in file_errors:
                        if error_type == "CRITICAL":
                            self.log_error(error_msg, str(py_file), line_no, "CRITICAL", error_type)
                        elif error_type == "ENCODING":
                            self.log_error(error_msg, str(py_file), line_no, "ERROR", error_type)
                            encoding_errors += 1
                        elif error_type == "SYNTAX":
                            self.log_error(error_msg, str(py_file), line_no, "ERROR", error_type)
                            syntax_errors += 1
                        elif error_type in ["PATTERN", "IMPORT", "QUALITY", "SECURITY"]:
                            self.log_error(error_msg, str(py_file), line_no, "ERROR", error_type)
                            pattern_errors += 1
                        
                except Exception as e:
                    self.log_error(f"فشل تحليل الملف: {e}", str(py_file), severity="CRITICAL", category="ANALYSIS")
        
        self.total_files_checked = len(self.python_files)
        
        total_errors = syntax_errors + encoding_errors + pattern_errors
        if total_errors == 0:
            self.log_info(f"✅ جميع الملفات ({len(self.python_files)}) صحيحة - {self.total_lines_checked} سطر تم فحصه", "SYNTAX")
            return True
        else:
            self.log_error(f"وجد {total_errors} خطأ: {syntax_errors} نحوية، {encoding_errors} ترميز، {pattern_errors} أنماط", severity="ERROR", category="SYNTAX")
            return False