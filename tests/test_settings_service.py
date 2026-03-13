import json

import services.settings_service as settings_module
from services.settings_service import SettingsService


def test_normalize_payment_methods_replaces_legacy_defaults():
    legacy = [
        {"name": "نقدي", "description": "الدفع النقدي", "details": "", "active": True},
        {"name": "تحويل بنكي", "description": "تحويل عبر البنك", "details": "", "active": True},
        {
            "name": "انستاباي",
            "description": "تحويل عبر انستاباي",
            "details": "",
            "active": False,
        },
    ]

    normalized, changed = SettingsService.normalize_payment_methods(legacy)

    assert changed is True
    assert [method["name"] for method in normalized] == [
        "VF Cash",
        "InstaPay",
        "Bank Misr Local",
        "Bank Misr Intl",
        "Cash",
    ]
    assert normalized[1]["details"] == "01067894321 - حازم أشرف\nskywaveads@instapay"
    assert normalized[3]["details"].endswith("SWIFT CODE: BMISEGCXXXX")
    assert normalized[4]["details"] == "الخزنة النقدية - مقر الشركة"


def test_normalize_payment_methods_preserves_custom_configuration():
    custom = [
        {
            "name": "رابط دفع خاص",
            "description": "بوابة دفع",
            "details": "https://pay.example.test/session/123",
            "active": True,
        }
    ]

    normalized, changed = SettingsService.normalize_payment_methods(custom)

    assert changed is False
    assert normalized == custom


def test_normalize_payment_methods_appends_missing_canonical_cash_method():
    current = [
        {
            "name": "فودافون كاش",
            "description": "تحويل عبر فودافون كاش",
            "details": "01067894321 - حازم أشرف",
            "active": True,
        },
        {
            "name": "إنستا باي",
            "description": "تحويل عبر إنستا باي",
            "details": "skywaveads@instapay",
            "active": True,
        },
        {
            "name": "تحويل بنكي داخل مصر",
            "description": "بنك مصر - تحويل محلي",
            "details": "رقم الحساب: 2630333000086626",
            "active": True,
        },
        {
            "name": "تحويل بنكي من خارج مصر",
            "description": "بنك مصر - تحويل من خارج مصر",
            "details": "IBAN: EG020002026302630333000086626",
            "active": True,
        },
    ]

    normalized, changed = SettingsService.normalize_payment_methods(current)

    assert changed is True
    assert [method["name"] for method in normalized] == [
        "VF Cash",
        "InstaPay",
        "Bank Misr Local",
        "Bank Misr Intl",
        "Cash",
    ]
    assert normalized[-1]["details"] == "الخزنة النقدية - مقر الشركة"


def test_update_setting_refreshes_settings_content_hash(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    local_settings_file = tmp_path / "local_settings.json"

    monkeypatch.setattr(SettingsService, "SETTINGS_FILE", str(settings_file))
    monkeypatch.setattr(settings_module, "_LOCAL_SETTINGS_FILE", str(local_settings_file))

    service = SettingsService()
    original_hash = service.get_setting("settings_content_hash")

    service.update_setting(
        "payment_methods",
        [
            {
                "name": "بوابة دفع",
                "description": "اختبار",
                "details": "ref-123",
                "active": True,
            }
        ],
    )

    persisted = json.loads(settings_file.read_text(encoding="utf-8"))
    expected_hash = service._compute_settings_hash(service._build_cloud_payload(persisted))

    assert persisted["settings_content_hash"] == expected_hash
    assert persisted["settings_content_hash"] != original_hash
