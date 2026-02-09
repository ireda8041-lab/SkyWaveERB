from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Finding:
    severity: str
    title: str
    details: str
    file: str | None = None


def _safe_print(line: str) -> None:
    """Print defensively on Windows consoles that cannot encode Arabic/Unicode text."""
    try:
        print(line)
    except UnicodeEncodeError:
        encoding = (sys.stdout.encoding or "utf-8").lower()
        try:
            sys.stdout.buffer.write((line + "\n").encode(encoding, errors="replace"))
        except Exception:
            sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="strict")
    except Exception:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None


def _load_json(path: Path) -> tuple[dict | list | None, str | None]:
    text = _read_text(path)
    if text is None:
        return None, "تعذر قراءة الملف كنص UTF-8"
    try:
        return json.loads(text), None
    except Exception as e:
        return None, str(e)


def _load_toml(path: Path) -> tuple[dict | None, str | None]:
    try:
        import tomllib
    except Exception:
        return None, "tomllib غير متاح"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), None
    except Exception as e:
        return None, str(e)


def _extract_py_version(version_py: Path) -> str | None:
    text = _read_text(version_py)
    if not text:
        return None
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    return m.group(1) if m else None


def audit_configs(root: Path) -> list[Finding]:
    findings: list[Finding] = []

    json_files = [
        "sync_config.json",
        "update_settings.json",
        "version.json",
        "skywave_settings.json",
        "custom_fields.json",
        "local_settings.json",
        "last_maintenance.json",
    ]

    for name in json_files:
        p = root / name
        if not p.exists():
            continue
        data, err = _load_json(p)
        if err:
            findings.append(
                Finding(
                    severity="high",
                    title="JSON غير صالح",
                    details=f"فشل parsing: {err}",
                    file=str(p),
                )
            )
            continue

        if name == "sync_config.json":
            if not isinstance(data, dict):
                findings.append(
                    Finding(
                        severity="high",
                        title="sync_config.json غير متوقع",
                        details="يجب أن يكون JSON object",
                        file=str(p),
                    )
                )
            else:
                required = ["enabled", "tables_to_sync", "batch_size", "timeout"]
                missing = [k for k in required if k not in data]
                if missing:
                    findings.append(
                        Finding(
                            severity="high",
                            title="نقص مفاتيح في sync_config.json",
                            details="المفاتيح المفقودة: " + ", ".join(missing),
                            file=str(p),
                        )
                    )

        if name == "local_settings.json" and isinstance(data, dict):
            if (
                "mongo_uri" in data
                and isinstance(data["mongo_uri"], str)
                and "@" in data["mongo_uri"]
            ):
                findings.append(
                    Finding(
                        severity="critical",
                        title="بيانات اتصال حساسة داخل local_settings.json",
                        details="تم العثور على mongo_uri يحتوي بيانات اعتماد داخل المشروع.",
                        file=str(p),
                    )
                )

    env_example = root / ".env.example"
    if env_example.exists():
        text = _read_text(env_example) or ""
        if "MONGO_URI=" not in text:
            findings.append(
                Finding(
                    severity="high",
                    title="غياب MONGO_URI في .env.example",
                    details="يوصى بتوفير متغير البيئة المستخدم فعلياً في التطبيق.",
                    file=str(env_example),
                )
            )

    pyproject = root / "pyproject.toml"
    pyproject_version = None
    if pyproject.exists():
        toml_data, err = _load_toml(pyproject)
        if err:
            findings.append(
                Finding(
                    severity="high",
                    title="pyproject.toml غير صالح",
                    details=f"فشل parsing: {err}",
                    file=str(pyproject),
                )
            )
        else:
            pyproject_version = (
                (toml_data or {}).get("project", {}).get("version")
                if isinstance(toml_data, dict)
                else None
            )

    version_py = root / "version.py"
    runtime_version = _extract_py_version(version_py) if version_py.exists() else None

    version_json = root / "version.json"
    version_json_version = None
    if version_json.exists():
        data, _ = _load_json(version_json)
        if isinstance(data, dict):
            version_json_version = data.get("version")

    versions = {
        "pyproject.toml": pyproject_version,
        "version.py": runtime_version,
        "version.json": version_json_version,
    }
    if len({v for v in versions.values() if v}) > 1:
        details = ", ".join(f"{k}={v}" for k, v in versions.items() if v)
        findings.append(
            Finding(
                severity="medium",
                title="عدم اتساق أرقام الإصدارات",
                details=details,
                file=None,
            )
        )

    return findings


def scan_secrets(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    patterns = [
        (re.compile(r"mongodb://[^\\s]+:[^\\s]+@"), "MongoDB URI مع بيانات اعتماد"),
        (re.compile(r"SkywavePassword\\d*"), "كلمة مرور Skywave"),
        (re.compile(r"AIzaSy[0-9A-Za-z_-]{20,}"), "مفتاح Google API محتمل"),
    ]

    exclude_dirs = {
        ".venv",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".hypothesis",
        "build",
        "dist",
        "installer_output",
        "exports",
        "tests",
        "tools",
    }
    include_ext = {".py", ".json", ".toml", ".md", ".iss", ".ps1", ".bat", ".txt"}

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for filename in filenames:
            p = Path(dirpath) / filename
            if p.suffix.lower() not in include_ext:
                continue
            if p.name == "audit_project.py":
                continue
            text = _read_text(p)
            if not text:
                continue
            for rx, title in patterns:
                if rx.search(text):
                    findings.append(
                        Finding(
                            severity="critical",
                            title=f"تسريب محتمل: {title}",
                            details="تم العثور على نمط حساس داخل ملف نصي.",
                            file=str(p),
                        )
                    )
                    break

    return findings


def main(argv: list[str]) -> int:
    root = Path(argv[1]).resolve() if len(argv) > 1 else Path(__file__).resolve().parent.parent
    findings = []
    findings.extend(audit_configs(root))
    findings.extend(scan_secrets(root))

    by_sev = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: (by_sev.get(f.severity, 9), f.title, f.file or ""))

    if not findings:
        _safe_print("OK: لا توجد مشاكل واضحة في configs أو أنماط أسرار ضمن نطاق الفحص.")
        return 0

    _safe_print("Findings:")
    for f in findings:
        loc = f" ({f.file})" if f.file else ""
        _safe_print(f"- [{f.severity}] {f.title}{loc}")
        _safe_print(f"  {f.details}")
    return 1 if any(f.severity in {"critical", "high"} for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
