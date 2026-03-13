import base64
import hashlib
import json
import os
from datetime import datetime
from typing import Any

from core.device_identity import get_stable_device_id

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


# استخدام مجلد AppData للمستخدم بدلاً من مجلد البرنامج (لتجنب مشاكل الصلاحيات في Program Files)
_APP_DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "SkyWaveERP")
os.makedirs(_APP_DATA_DIR, exist_ok=True)

# ملف الإعدادات المحلي في مجلد المشروع
_LOCAL_SETTINGS_FILE = "skywave_settings.json"

DEFAULT_PAYMENT_METHODS: list[dict[str, Any]] = [
    {
        "name": "VF Cash",
        "description": "Vodafone Cash transfer",
        "details": "01067894321 - حازم أشرف\n01021965200 - رضا سامي",
        "active": True,
    },
    {
        "name": "InstaPay",
        "description": "InstaPay transfer",
        "details": "01067894321 - حازم أشرف\nskywaveads@instapay",
        "active": True,
    },
    {
        "name": "Bank Misr Local",
        "description": "Local bank transfer",
        "details": "رقم الحساب: 2630333000086626\nSWIFT CODE: BMISEGCXXXX",
        "active": True,
    },
    {
        "name": "Bank Misr Intl",
        "description": "International bank transfer",
        "details": "IBAN: EG020002026302630333000086626\nSWIFT CODE: BMISEGCXXXX",
        "active": True,
    },
    {
        "name": "Cash",
        "description": "Cash payment",
        "details": "الخزنة النقدية - مقر الشركة",
        "active": True,
    },
]
_LEGACY_PAYMENT_METHOD_NAMES = {
    "cash",
    "instapay",
    "bank transfer",
    "نقدي",
    "تحويل بنكي",
    "انستاباي",
    "تحويل بنكي دولي",
    "فودافون كاش",
    "إنستا باي",
    "تحويل بنكي داخل مصر",
    "تحويل بنكي من خارج مصر",
    "دفع نقدي",
}


class SettingsService:
    """قسم الإعدادات المسؤول عن حفظ وقراءة إعدادات التطبيق."""

    SETTINGS_FILE = os.path.join(_APP_DATA_DIR, "skywave_settings.json")
    CLOUD_EXCLUDED_KEYS = {"company_logo_path"}
    CLOUD_META_KEYS = {"settings_last_modified", "settings_content_hash"}

    DEFAULT_SETTINGS = {
        "company_name": "Sky Wave",
        "company_tagline": "وكالة تسويق رقمي متكاملة",
        "company_address": "القاهرة، مصر",
        "company_phone": "+20 10 123 4567",
        "company_email": "info@skywave.agency",
        "bank_name": "البنك الأهلي المصري",
        "bank_account": "XXXX-XXXX-XXXX-XXXX",
        "vodafone_cash": "010-XXXX-XXXX",
        "default_tax_rate": 0.0,
        "default_notes": "شكراً لثقتكم في Sky Wave. نسعد بخدمتكم دائماً.",
        "company_logo_path": "",
        "company_logo_data": "",  # ⚡ اللوجو كـ Base64 للمزامنة بين الأجهزة
        "print_client_logo_width_px": 120,
        "print_client_logo_max_height_px": 40,
        "print_client_logo_max_width_percent": 22,
        "settings_last_modified": "",
    }

    def __init__(self):
        self.repo = None
        self.settings = self.load_settings()
        self._merge_local_settings()
        self._normalize_runtime_settings()
        safe_print("INFO: قسم الإعدادات (SettingsService) جاهز.")

    def _touch_settings(self) -> None:
        self.settings["settings_last_modified"] = datetime.now().isoformat()

    @staticmethod
    def default_payment_methods() -> list[dict[str, Any]]:
        return [dict(method) for method in DEFAULT_PAYMENT_METHODS]

    @classmethod
    def normalize_payment_methods(cls, value: Any) -> tuple[list[dict[str, Any]], bool]:
        if not isinstance(value, list) or not value:
            return cls.default_payment_methods(), True

        normalized: list[dict[str, Any]] = []
        has_legacy_names = False
        changed = False

        for item in value:
            if not isinstance(item, dict):
                changed = True
                continue

            name = str(item.get("name") or "").strip()
            description = str(item.get("description") or "").strip()
            details = str(item.get("details") or "").strip()
            active = bool(item.get("active", True))

            if not name and not description and not details:
                changed = True
                continue

            if name.casefold() in _LEGACY_PAYMENT_METHOD_NAMES:
                has_legacy_names = True

            normalized_item = {
                "name": name,
                "description": description,
                "details": details,
                "active": active,
            }
            if normalized_item != item:
                changed = True
            normalized.append(normalized_item)

        if not normalized or has_legacy_names:
            return cls.default_payment_methods(), True

        canonical_defaults = cls.default_payment_methods()
        canonical_names = [str(method.get("name") or "").strip() for method in canonical_defaults]
        canonical_set = {name for name in canonical_names if name}
        current_by_name = {
            str(method.get("name") or "").strip(): dict(method)
            for method in normalized
            if str(method.get("name") or "").strip()
        }
        if current_by_name and all(name in canonical_set for name in current_by_name):
            missing_names = [name for name in canonical_names if name not in current_by_name]
            if missing_names:
                merged_methods: list[dict[str, Any]] = []
                for default_method in canonical_defaults:
                    default_name = str(default_method.get("name") or "").strip()
                    merged_methods.append(dict(current_by_name.get(default_name) or default_method))
                return merged_methods, True

        return normalized, changed

    def _normalize_runtime_settings(self) -> None:
        updated = False

        payment_methods, changed = self.normalize_payment_methods(
            self.settings.get("payment_methods")
        )
        if changed or self.settings.get("payment_methods") != payment_methods:
            self.settings["payment_methods"] = payment_methods
            updated = True

        if updated:
            self._touch_settings()
            self.save_settings(self.settings)

    @classmethod
    def _build_cloud_payload(cls, source: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for key, value in source.items():
            if key in cls.CLOUD_EXCLUDED_KEYS:
                continue
            if key in cls.CLOUD_META_KEYS:
                continue
            payload[key] = value
        return payload

    @staticmethod
    def _compute_settings_hash(payload: dict[str, Any]) -> str:
        try:
            normalized = json.dumps(
                payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        except Exception:
            normalized = str(payload)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def set_repository(self, repository) -> None:
        self.repo = repository

    def _merge_local_settings(self):
        """⚡ دمج الإعدادات من الملف المحلي (يحدث القيم الموجودة)"""
        try:
            if os.path.exists(_LOCAL_SETTINGS_FILE):
                safe_print(
                    f"INFO: [SettingsService] جاري تحميل الإعدادات من {_LOCAL_SETTINGS_FILE}"
                )
                with open(_LOCAL_SETTINGS_FILE, encoding="utf-8") as f:
                    local_settings = json.load(f)

                # ⚡ تحديث كل القيم من الملف المحلي (له الأولوية)
                updated_count = 0
                for key, value in local_settings.items():
                    if key not in self.settings or self.settings[key] != value:
                        self.settings[key] = value
                        updated_count += 1

                if updated_count > 0:
                    safe_print(
                        f"INFO: [SettingsService] ✅ تم تحديث {updated_count} إعداد من الملف المحلي"
                    )
                    # حفظ الإعدادات المدمجة
                    self.save_settings(self.settings)
        except Exception as e:
            safe_print(f"WARNING: [SettingsService] فشل قراءة الملف المحلي: {e}")

    def load_settings(self) -> dict[str, Any]:
        if os.path.exists(self.SETTINGS_FILE):
            try:
                with open(self.SETTINGS_FILE, encoding="utf-8") as f:
                    settings = json.load(f)
                for key, value in self.DEFAULT_SETTINGS.items():
                    if key not in settings:
                        settings[key] = value
                return dict(settings)
            except Exception as e:
                safe_print(
                    f"ERROR: [SettingsService] فشل تحميل ملف الإعدادات: {e}. سيتم استخدام الافتراضي."
                )
                return dict(self.DEFAULT_SETTINGS)
        else:
            safe_print("INFO: [SettingsService] ملف الإعدادات غير موجود. سيتم إنشاؤه.")
            self.save_settings(self.DEFAULT_SETTINGS)
            return dict(self.DEFAULT_SETTINGS)

    def save_settings(self, settings_data: dict[str, Any]):
        try:
            prepared_settings = dict(settings_data)
            payload_core = self._build_cloud_payload(prepared_settings)
            prepared_settings["settings_content_hash"] = self._compute_settings_hash(payload_core)
            with open(self.SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(prepared_settings, f, ensure_ascii=False, indent=4)
            self.settings = prepared_settings
            safe_print("INFO: [SettingsService] تم حفظ الإعدادات بنجاح.")
        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل حفظ الإعدادات: {e}")
            raise

    def get_settings(self) -> dict[str, Any]:
        return dict(self.settings)

    def get_setting(self, key: str) -> Any:
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def update_setting(self, key: str, value: Any):
        """تحديث إعداد معين وحفظه"""
        self.settings[key] = value
        self._touch_settings()
        self.save_settings(self.settings)
        try:
            repo = getattr(self, "repo", None)
            if (
                repo
                and getattr(repo, "online", False)
                and getattr(repo, "mongo_db", None) is not None
            ):
                self.sync_settings_to_cloud(
                    repo,
                    emit_notification=True,
                    silent_notification=True,
                )
        except Exception as exc:
            safe_print(f"WARNING: [SettingsService] تعذر مزامنة الإعداد '{key}' إلى السحابة: {exc}")

    def update_settings(self, new_settings: dict[str, Any]):
        if not isinstance(new_settings, dict):
            return
        for k, v in new_settings.items():
            self.settings[k] = v
        self._touch_settings()
        self.save_settings(self.settings)
        try:
            repo = getattr(self, "repo", None)
            if (
                repo
                and getattr(repo, "online", False)
                and getattr(repo, "mongo_db", None) is not None
            ):
                self.sync_settings_to_cloud(
                    repo,
                    emit_notification=True,
                    silent_notification=True,
                )
        except Exception as exc:
            safe_print(f"WARNING: [SettingsService] تعذر مزامنة دفعة إعدادات إلى السحابة: {exc}")

    # ==========================================
    # ⚡ دوال اللوجو - للمزامنة بين الأجهزة
    # ==========================================

    def save_logo_from_file(self, file_path: str) -> bool:
        """
        حفظ اللوجو من ملف كـ Base64
        يتم تخزينه في الإعدادات للمزامنة بين الأجهزة
        """
        try:
            if not file_path or not os.path.exists(file_path):
                return False

            with open(file_path, "rb") as f:
                logo_bytes = f.read()

            # تحويل لـ Base64
            logo_base64 = base64.b64encode(logo_bytes).decode("utf-8")

            # حفظ في الإعدادات
            self.settings["company_logo_data"] = logo_base64
            self.settings["company_logo_path"] = file_path  # للعرض المحلي
            self._touch_settings()
            self.save_settings(self.settings)

            safe_print(f"INFO: [SettingsService] تم حفظ اللوجو ({len(logo_base64)} حرف)")
            return True

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل حفظ اللوجو: {e}")
            return False

    def get_logo_as_pixmap(self):
        """
        الحصول على اللوجو كـ QPixmap
        يحاول أولاً من Base64، ثم من المسار المحلي
        """
        try:
            from PyQt6.QtCore import QByteArray
            from PyQt6.QtGui import QPixmap

            # أولاً: محاولة تحميل من Base64 (للمزامنة)
            logo_data = self.settings.get("company_logo_data", "")
            if logo_data:
                try:
                    logo_bytes = base64.b64decode(logo_data)
                    pixmap = QPixmap()
                    pixmap.loadFromData(QByteArray(logo_bytes))
                    if not pixmap.isNull():
                        return pixmap
                except Exception as e:
                    safe_print(f"WARNING: [SettingsService] فشل تحميل اللوجو من Base64: {e}")

            # ثانياً: محاولة تحميل من المسار المحلي
            logo_path = self.settings.get("company_logo_path", "")
            if logo_path and os.path.exists(logo_path):
                pixmap = QPixmap(logo_path)
                if not pixmap.isNull():
                    return pixmap

            return None

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل تحميل اللوجو: {e}")
            return None

    def clear_logo(self):
        """مسح اللوجو"""
        self.settings["company_logo_data"] = ""
        self.settings["company_logo_path"] = ""
        self._touch_settings()
        self.save_settings(self.settings)
        safe_print("INFO: [SettingsService] تم مسح اللوجو")

    # ==========================================
    # ⚡ مزامنة الإعدادات مع MongoDB
    # ==========================================

    def sync_settings_to_cloud(
        self,
        repository,
        emit_notification: bool = False,
        silent_notification: bool = True,
    ) -> bool:
        """رفع الإعدادات للسحابة"""
        try:
            if not repository or not repository.online or repository.mongo_db is None:
                return False

            # حفظ الإعدادات في مجموعة system_settings
            collection = repository.mongo_db["system_settings"]

            payload_core = self._build_cloud_payload(self.settings)
            payload_hash = self._compute_settings_hash(payload_core)

            remote_doc = collection.find_one({"_id": "company_settings"}) or {}
            remote_hash = str(remote_doc.get("settings_content_hash") or "")
            if not remote_hash:
                remote_core = {
                    k: v
                    for k, v in remote_doc.items()
                    if k not in {"_id"} | self.CLOUD_META_KEYS | self.CLOUD_EXCLUDED_KEYS
                }
                remote_hash = self._compute_settings_hash(remote_core) if remote_core else ""

            if remote_hash and remote_hash == payload_hash:
                remote_stamp = str(remote_doc.get("settings_last_modified") or "")
                local_changed = False
                if remote_stamp and self.settings.get("settings_last_modified") != remote_stamp:
                    self.settings["settings_last_modified"] = remote_stamp
                    local_changed = True
                if self.settings.get("settings_content_hash") != payload_hash:
                    self.settings["settings_content_hash"] = payload_hash
                    local_changed = True
                if local_changed:
                    self.save_settings(self.settings)
                return True

            stamp = datetime.now().isoformat()
            payload = dict(payload_core)
            payload["settings_last_modified"] = stamp
            payload["settings_content_hash"] = payload_hash

            self.settings["settings_last_modified"] = stamp
            self.settings["settings_content_hash"] = payload_hash
            self.save_settings(self.settings)

            collection.update_one({"_id": "company_settings"}, {"$set": payload}, upsert=True)

            # system_settings notification is silent by default to avoid noisy startup toasts.
            if emit_notification:
                try:
                    notifications = repository.mongo_db["notifications"]
                    notifications.insert_one(
                        {
                            "message": "تم تحديث إعدادات النظام",
                            "type": "info",
                            "title": "⚙️ الإعدادات",
                            "device_id": get_stable_device_id(),
                            "created_at": stamp,
                            "entity_type": "system_settings",
                            "action": "updated",
                            "silent": bool(silent_notification),
                        }
                    )
                except Exception as exc:
                    safe_print(
                        f"WARNING: [SettingsService] تعذر إنشاء إشعار تحديث الإعدادات: {exc}"
                    )

            safe_print("INFO: [SettingsService] ✅ تم رفع الإعدادات للسحابة")
            return True

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل رفع الإعدادات للسحابة: {e}")
            return False

    def sync_settings_from_cloud(self, repository) -> bool:
        """تحميل الإعدادات من السحابة"""
        try:
            if not repository or not repository.online or repository.mongo_db is None:
                return False

            collection = repository.mongo_db["system_settings"]
            cloud_settings = collection.find_one({"_id": "company_settings"})

            if not cloud_settings:
                # First writer wins without noisy notifications.
                return self.sync_settings_to_cloud(repository, emit_notification=False)

            cloud_settings = dict(cloud_settings)
            cloud_settings.pop("_id", None)

            local_stamp = str(self.settings.get("settings_last_modified") or "")
            remote_stamp = str(cloud_settings.get("settings_last_modified") or "")

            local_dt = self._parse_settings_timestamp(local_stamp)
            remote_dt = self._parse_settings_timestamp(remote_stamp)

            local_core = self._build_cloud_payload(self.settings)
            remote_core = {
                k: v
                for k, v in cloud_settings.items()
                if k not in self.CLOUD_META_KEYS and k not in self.CLOUD_EXCLUDED_KEYS
            }
            local_hash = self._compute_settings_hash(local_core)
            remote_hash = str(cloud_settings.get("settings_content_hash") or "")
            if not remote_hash:
                remote_hash = self._compute_settings_hash(remote_core)

            if local_hash == remote_hash:
                updated = False
                if remote_stamp and self.settings.get("settings_last_modified") != remote_stamp:
                    self.settings["settings_last_modified"] = remote_stamp
                    updated = True
                if self.settings.get("settings_content_hash") != remote_hash:
                    self.settings["settings_content_hash"] = remote_hash
                    updated = True
                if updated:
                    self.save_settings(self.settings)
                return True

            if local_dt and remote_dt and local_dt > remote_dt:
                return self.sync_settings_to_cloud(repository, emit_notification=False)

            # دمج الإعدادات (السحابة تأخذ الأولوية) مع تجاهل الحقول المحلية الخاصة بالجهاز.
            for key, value in cloud_settings.items():
                if key in self.CLOUD_EXCLUDED_KEYS:
                    continue
                self.settings[key] = value
            self.settings["settings_content_hash"] = remote_hash
            if remote_stamp:
                self.settings["settings_last_modified"] = remote_stamp

            self.save_settings(self.settings)

            try:
                from core.signals import app_signals

                app_signals.system_changed.emit()
            except Exception as exc:
                safe_print(
                    f"WARNING: [SettingsService] تعذر بث system_changed بعد مزامنة الإعدادات: {exc}"
                )

            safe_print("INFO: [SettingsService] ✅ تم تحميل الإعدادات من السحابة")
            return True

        except Exception as e:
            safe_print(f"ERROR: [SettingsService] فشل تحميل الإعدادات من السحابة: {e}")
            return False

    @staticmethod
    def _parse_settings_timestamp(value: str) -> datetime | None:
        try:
            if not value:
                return None
            return datetime.fromisoformat(value)
        except Exception:
            return None
