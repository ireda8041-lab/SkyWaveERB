import hashlib

import pytest

import updater


def test_validate_update_url_allows_github_https():
    url = "https://github.com/ireda8041-lab/SkyWaveERB/releases/download/v2.1.0/SkyWaveERP-Setup-2.1.0.exe"
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
