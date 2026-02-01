"""
مدير الحقول المخصصة - لحفظ واسترجاع القيم المخصصة
Custom Fields Manager - Save and retrieve custom values
"""

import json
import os
import shutil
import sys
import tempfile

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


class CustomFieldsManager:
    """مدير الحقول المخصصة - Singleton"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        data_dir = os.environ.get("SKYWAVEERP_DATA_DIR") or os.path.join(
            os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
            "SkyWaveERP",
        )
        os.makedirs(data_dir, exist_ok=True)
        self._file_path = os.path.join(data_dir, "custom_fields.json")
        if not os.path.exists(self._file_path):
            legacy_paths = [os.path.join(os.getcwd(), "custom_fields.json")]
            if getattr(sys, "frozen", False):
                legacy_paths.append(
                    os.path.join(os.path.dirname(sys.executable), "custom_fields.json")
                )
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                legacy_paths.append(os.path.join(project_root, "custom_fields.json"))
            for legacy in legacy_paths:
                if (
                    legacy
                    and os.path.exists(legacy)
                    and os.path.abspath(legacy) != os.path.abspath(self._file_path)
                ):
                    try:
                        shutil.copy2(legacy, self._file_path)
                        break
                    except Exception as e:
                        safe_print(f"WARNING: [CustomFieldsManager] فشل نقل الملف القديم: {e}")
        self._data = {
            "business_fields": [],  # مجالات العمل
            "service_categories": [],  # فئات الخدمات
            "project_types": [],  # أنواع المشاريع
            "payment_methods": [],  # طرق الدفع
            "countries": [],  # الدول
            "cities": [],  # المدن
        }
        self._load()

    def _load(self):
        """تحميل البيانات من الملف"""
        try:
            if os.path.exists(self._file_path):
                with open(self._file_path, encoding="utf-8") as f:
                    loaded = json.load(f)
                    for key in self._data:
                        if key in loaded:
                            self._data[key] = loaded[key]
        except Exception as e:
            safe_print(f"WARNING: [CustomFieldsManager] فشل تحميل البيانات: {e}")

    def _save(self):
        """حفظ البيانات في الملف"""
        tmp_path = None
        try:
            dir_name = os.path.dirname(self._file_path) or "."
            os.makedirs(dir_name, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(prefix="custom_fields_", suffix=".tmp", dir=dir_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self._file_path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        except Exception as e:
            safe_print(f"ERROR: [CustomFieldsManager] فشل حفظ البيانات: {e}")

    def add_value(self, field_name: str, value: str) -> bool:
        """إضافة قيمة جديدة لحقل معين"""
        if not value or not value.strip():
            return False

        value = value.strip()

        if field_name not in self._data:
            self._data[field_name] = []

        if value not in self._data[field_name]:
            self._data[field_name].append(value)
            self._save()
            return True
        return False

    def get_values(self, field_name: str) -> list[str]:
        """الحصول على القيم المخصصة لحقل معين"""
        return self._data.get(field_name, [])

    def remove_value(self, field_name: str, value: str) -> bool:
        """حذف قيمة من حقل معين"""
        if field_name in self._data and value in self._data[field_name]:
            self._data[field_name].remove(value)
            self._save()
            return True
        return False

    def get_all_business_fields(self) -> list[str]:
        """الحصول على جميع مجالات العمل (الافتراضية + المخصصة)"""
        default_fields = [
            # === التجارة ===
            "تجارة عامة",
            "تجارة إلكترونية",
            "تجارة جملة",
            "تجارة تجزئة",
            "استيراد وتصدير",
            "توزيع وتوريدات",
            # === التقنية والبرمجيات ===
            "تقنية المعلومات",
            "تطوير البرمجيات",
            "تصميم مواقع",
            "تطبيقات الجوال",
            "استضافة وسيرفرات",
            "أمن المعلومات",
            "الذكاء الاصطناعي",
            # === الخدمات المهنية ===
            "استشارات إدارية",
            "استشارات مالية",
            "استشارات قانونية",
            "محاسبة ومراجعة",
            "موارد بشرية",
            "تدريب وتطوير",
            # === التصميم والإبداع ===
            "تصميم جرافيك",
            "تصميم داخلي",
            "إنتاج فيديو",
            "تصوير فوتوغرافي",
            "طباعة ونشر",
            "إعلان وتسويق",
            "علاقات عامة",
            # === البناء والعقارات ===
            "مقاولات عامة",
            "تشطيبات",
            "ديكور",
            "عقارات",
            "تطوير عقاري",
            "هندسة معمارية",
            "هندسة مدنية",
            # === الصناعة ===
            "صناعة غذائية",
            "صناعة ملابس",
            "صناعة أثاث",
            "صناعة معدنية",
            "صناعة بلاستيك",
            "صناعة كيماوية",
            # === الصحة والطب ===
            "مستشفيات",
            "عيادات طبية",
            "صيدليات",
            "مستلزمات طبية",
            "مختبرات",
            "تجميل وعناية",
            # === التعليم ===
            "مدارس",
            "جامعات ومعاهد",
            "مراكز تدريب",
            "تعليم إلكتروني",
            "حضانات",
            # === السياحة والضيافة ===
            "فنادق",
            "مطاعم وكافيهات",
            "سياحة وسفر",
            "تنظيم فعاليات",
            "ترفيه",
            # === النقل والخدمات اللوجستية ===
            "نقل بري",
            "نقل بحري",
            "نقل جوي",
            "شحن وتخليص",
            "توصيل",
            # === الزراعة ===
            "زراعة",
            "تربية حيوانات",
            "منتجات زراعية",
            "مستلزمات زراعية",
            # === الطاقة ===
            "طاقة شمسية",
            "طاقة متجددة",
            "نفط وغاز",
            "كهرباء",
            # === المالية ===
            "بنوك",
            "تأمين",
            "استثمار",
            "صرافة",
            "تمويل",
            # === أخرى ===
            "خدمات عامة",
            "صيانة",
            "تنظيف",
            "أمن وحراسة",
            "أخرى",
        ]

        # دمج المجالات الافتراضية مع المخصصة
        custom = self.get_values("business_fields")
        all_fields = list(
            dict.fromkeys(default_fields + custom)
        )  # إزالة التكرار مع الحفاظ على الترتيب
        return all_fields


# Instance عام للاستخدام في كل البرنامج
custom_fields = CustomFieldsManager()
