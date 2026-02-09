import hashlib

import pytest

import updater


def test_validate_update_url_allows_github_https():
    url = "https://github.com/ireda8041-lab/SkyWaveERB/releases/download/v2.1.0/SkyWaveERP-Setup-2.1.0.exe"
    assert updater._validate_update_url(url) == url


def test_validate_update_url_allows_release_assets_https():
    url = "https://release-assets.githubusercontent.com/github-production-release-asset/1/2?sp=r"
    assert updater._validate_update_url(url) == url


def test_validate_update_url_rejects_http():
    with pytest.raises(ValueError):
        updater._validate_update_url("http://github.com/ireda8041-lab/SkyWaveERB/releases")


def test_validate_update_url_rejects_unlisted_host():
    with pytest.raises(ValueError):
        updater._validate_update_url("https://example.com/update.exe")


def test_sha256_helpers(tmp_path):
    p = tmp_path / "payload.bin"
    p.write_bytes(b"abc")
    expected = hashlib.sha256(b"abc").hexdigest()
    assert updater._sha256_file(str(p)) == expected
    assert updater._normalize_sha256("sha256:" + expected) == expected
    assert updater._normalize_sha256(expected.upper()) == expected
    assert updater._normalize_sha256("not-a-sha") is None


def test_resolve_setup_path_finds_legacy_name(tmp_path):
    legacy = tmp_path / "SkyWave-Setup-Update.exe"
    legacy.write_bytes(b"fake-setup")

    resolved, candidates = updater._resolve_setup_path("missing.exe", str(tmp_path))

    assert resolved == str(legacy)
    assert str(legacy) in candidates
