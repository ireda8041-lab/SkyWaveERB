import os
import re
from pathlib import Path


def test_no_hardcoded_secrets_in_repo():
    project_root = Path(__file__).resolve().parent.parent

    critical_patterns = [
        re.compile(r"147\.79\.66\.116"),
        re.compile(r"SkywavePassword\d*"),
        re.compile(r"mongodb://[^\s:@/]+:[^\s@/]+@\d+\.\d+\.\d+\.\d+"),
    ]

    excluded_dirs = {
        ".git",
        ".venv",
        "tests",
        "tools",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".hypothesis",
        ".theORQL",
        "build",
        "dist",
        "installer_output",
        "exports",
    }
    included_ext = {".py", ".json", ".toml", ".md", ".iss", ".ps1", ".bat", ".txt"}

    matches: list[str] = []

    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [d for d in dirnames if d not in excluded_dirs]

        for filename in filenames:
            path = Path(dirpath) / filename
            if path.suffix.lower() not in included_ext:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

            for rx in critical_patterns:
                if rx.search(text):
                    rel = path.relative_to(project_root).as_posix()
                    matches.append(rel)
                    break

    assert not matches
