import json
import re
from pathlib import Path


def _read_pyproject_version(root: Path) -> str:
    import tomllib

    pyproject_data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    return str(pyproject_data["project"]["version"])


def _read_runtime_version(root: Path) -> str:
    text = (root / "version.py").read_text(encoding="utf-8")
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    assert match is not None, "version.py must define __version__"
    return match.group(1)


def _read_version_json(root: Path) -> dict:
    return json.loads((root / "version.json").read_text(encoding="utf-8"))


def test_version_files_are_consistent():
    root = Path(__file__).resolve().parents[1]
    pyproject_version = _read_pyproject_version(root)
    runtime_version = _read_runtime_version(root)
    version_json = _read_version_json(root)
    json_version = str(version_json["version"])

    assert pyproject_version == runtime_version == json_version


def test_version_json_url_matches_version():
    root = Path(__file__).resolve().parents[1]
    version_json = _read_version_json(root)
    version = str(version_json["version"])
    url = str(version_json.get("url", ""))

    assert f"v{version}" in url
    assert version in url
