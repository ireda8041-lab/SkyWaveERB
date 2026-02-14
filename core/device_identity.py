"""Utilities for stable per-device identity across app modules."""

from __future__ import annotations

import os
import platform
import re
import uuid
from pathlib import Path

_DEVICE_ID_FILE = ".skywave_device_id"


def _sanitize(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip())
    return cleaned.strip("-_").lower()


def _new_device_id() -> str:
    host = _sanitize(platform.node()) or "host"
    return f"{host}-{uuid.uuid4().hex[:10]}"


def get_stable_device_id() -> str:
    """
    Return a stable id for this installation/device.

    Behavior:
    - Reuses value from ~/.skywave_device_id if present.
    - Migrates short legacy ids to a stronger unique format.
    - Creates and persists a new id if missing.
    """
    device_file = Path(os.path.expanduser("~")) / _DEVICE_ID_FILE

    try:
        if device_file.exists():
            current = device_file.read_text(encoding="utf-8").strip()
            if current:
                lower_current = current.lower()
                looks_like_legacy_hash = (
                    "-" not in current
                    and re.fullmatch(r"[a-f0-9]{8,64}", lower_current) is not None
                )
                # Legacy ids were short hashes with high collision risk across devices.
                if len(current) < 12 or looks_like_legacy_hash:
                    upgraded = _new_device_id()
                    try:
                        device_file.write_text(upgraded, encoding="utf-8")
                    except OSError:
                        pass
                    return upgraded
                return current
    except Exception:
        pass

    generated = _new_device_id()
    try:
        device_file.write_text(generated, encoding="utf-8")
    except OSError:
        pass
    return generated
