from __future__ import annotations

import json
import os
from pathlib import Path

from pymongo import MongoClient


def resolve_uri() -> str:
    uri = os.environ.get("MONGO_URI")
    if uri:
        return uri

    cloud_cfg = Path("cloud_config.json")
    if cloud_cfg.exists():
        try:
            data = json.loads(cloud_cfg.read_text(encoding="utf-8"))
            cfg_uri = str(data.get("MONGO_URI") or "").strip()
            if cfg_uri:
                return cfg_uri
        except Exception:
            pass

    return "mongodb://127.0.0.1:27017"


def main() -> int:
    uri = resolve_uri()
    db_name = os.environ.get("MONGO_DB_NAME", "skywave_erp_db")
    client = MongoClient(uri, serverSelectionTimeoutMS=8000)
    db = client[db_name]

    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"Ping failed: {exc}")
        return 1

    try:
        with db["clients"].watch(max_await_time_ms=200, full_document="default") as stream:
            try:
                stream.try_next()
            except Exception:
                pass
        print("Change Streams supported: YES")
        return 0
    except Exception as exc:
        error_text = str(exc)
        print(f"Change Streams supported: NO ({error_text})")
        lowered = error_text.lower()
        if "only supported on replica sets" in lowered or "location40573" in lowered:
            print(
                "Hint: run `powershell -ExecutionPolicy Bypass -File tools/enable_local_replset.ps1` as Administrator."
            )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
