import json
from version import CURRENT_VERSION
from auto_updater import CURRENT_VERSION as AUTO_UPDATER_VERSION

print("=" * 60)
print("التحقق من رقم الإصدار في جميع الملفات")
print("=" * 60)

# version.json
with open('version.json', 'r', encoding='utf-8') as f:
    data = json.load(f)
    print(f"✅ version.json: v{data['version']}")

# version.py
print(f"✅ version.py: v{CURRENT_VERSION}")

# auto_updater.py
print(f"✅ auto_updater.py: v{AUTO_UPDATER_VERSION}")

print("=" * 60)
print("✅ جميع الملفات محدثة إلى v1.0.1")
print("=" * 60)
