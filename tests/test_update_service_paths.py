import os

from services.update_service import UpdateService


def test_update_service_uses_stable_staging_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    service = UpdateService("2.2.2", "https://example.invalid/version.json")

    assert service.temp_update_path.endswith("SkyWaveERP_Update.exe")
    assert service.legacy_temp_update_path.endswith("SkyWave-Setup-Update.exe")
    assert os.path.dirname(service.temp_update_path) == service.update_staging_dir
    assert os.path.dirname(service.legacy_temp_update_path) == service.update_staging_dir


def test_resolve_setup_path_falls_back_to_legacy_name(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    service = UpdateService("2.2.2", "https://example.invalid/version.json")

    os.makedirs(service.update_staging_dir, exist_ok=True)
    with open(service.legacy_temp_update_path, "wb") as f:
        f.write(b"legacy-setup")

    resolved = service._resolve_setup_path(service.temp_update_path)
    assert resolved == service.legacy_temp_update_path
