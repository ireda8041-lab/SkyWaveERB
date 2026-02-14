from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pymongo import MongoClient
from pymongo.errors import OperationFailure


def _safe_print(msg: str) -> None:
    try:
        print(msg)
    except UnicodeEncodeError:
        print(msg.encode("ascii", errors="ignore").decode())


def _extract_first_host(uri: str) -> str:
    parts = urlsplit(str(uri or "").strip())
    netloc = parts.netloc.split("@")[-1]
    first = netloc.split(",")[0].strip()
    if not first:
        return ""
    if ":" not in first:
        return f"{first}:27017"
    return first


def _ensure_replica_set_uri(uri: str, rs_name: str) -> str:
    uri = str(uri or "").strip()
    if not uri:
        return uri
    if not uri.lower().startswith("mongodb://"):
        return uri

    parts = urlsplit(uri)
    query_map = dict(parse_qsl(parts.query, keep_blank_values=True))
    if not query_map.get("replicaSet"):
        query_map["replicaSet"] = rs_name
    if "directConnection" not in query_map:
        query_map["directConnection"] = "false"

    rebuilt_query = urlencode(list(query_map.items()))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, rebuilt_query, parts.fragment))


def _update_cloud_config(path: Path, mongo_uri: str, db_name: str) -> None:
    data = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    data["MONGO_URI"] = mongo_uri
    data["MONGO_DB_NAME"] = db_name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _replace_or_append_env_line(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(line, content)
    if content and not content.endswith("\n"):
        content += "\n"
    return content + line + "\n"


def _update_env_file(path: Path, mongo_uri: str, db_name: str) -> None:
    text = ""
    if path.exists():
        text = path.read_text(encoding="utf-8")
    text = _replace_or_append_env_line(text, "MONGO_URI", mongo_uri)
    text = _replace_or_append_env_line(text, "MONGO_DB_NAME", db_name)
    path.write_text(text, encoding="utf-8")


def _wait_for_primary(client: MongoClient, rs_name: str, timeout_seconds: int) -> bool:
    deadline = time.time() + max(10, int(timeout_seconds))
    while time.time() < deadline:
        try:
            hello = client.admin.command("hello")
            if str(hello.get("setName") or "").strip() == rs_name and (
                hello.get("isWritablePrimary") or hello.get("ismaster")
            ):
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _resolve_db_name(default_db_name: str, app_uri: str) -> str:
    fallback = (default_db_name or "").strip() or "skywave_erp_db"
    uri = str(app_uri or "").strip()
    if not uri:
        return fallback
    try:
        parts = urlsplit(uri)
        db_name = parts.path.strip("/")
        return db_name or fallback
    except Exception:
        return fallback


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enable/verify MongoDB replica set on a remote server (requires admin privileges on Mongo)."
        )
    )
    parser.add_argument(
        "--admin-uri",
        required=True,
        help="Mongo URI for an admin/clusterAdmin user (used for replSet commands).",
    )
    parser.add_argument(
        "--app-uri",
        default=os.environ.get("MONGO_URI", ""),
        help="Application Mongo URI to normalize with replicaSet/directConnection settings.",
    )
    parser.add_argument("--replica-set-name", default="rs0")
    parser.add_argument(
        "--member-host",
        default="",
        help="Replica set member host:port. If omitted, inferred from hello.me or URI host.",
    )
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument(
        "--db-name",
        default=os.environ.get("MONGO_DB_NAME", "skywave_erp_db"),
        help="Database name for cloud_config/.env updates.",
    )
    parser.add_argument(
        "--write-cloud-config",
        action="store_true",
        help="Update cloud_config.json in current directory with normalized URI.",
    )
    parser.add_argument(
        "--write-env",
        action="store_true",
        help="Update .env in current directory with normalized URI.",
    )

    args = parser.parse_args()
    rs_name = str(args.replica_set_name or "rs0").strip() or "rs0"

    _safe_print("Connecting to Mongo admin...")
    try:
        client = MongoClient(args.admin_uri, serverSelectionTimeoutMS=10000, connectTimeoutMS=10000)
        client.admin.command("ping")
    except Exception as exc:
        _safe_print(f"ERROR: could not connect to Mongo admin endpoint: {exc}")
        return 1

    try:
        hello = client.admin.command("hello")
        active_set = str(hello.get("setName") or "").strip()
    except Exception as exc:
        _safe_print(f"ERROR: hello command failed: {exc}")
        return 1

    if active_set:
        _safe_print(f"Replica set already enabled: {active_set}")
        rs_name = active_set
    else:
        member_host = str(args.member_host or "").strip()
        if not member_host:
            member_host = str(hello.get("me") or "").strip()
        if not member_host:
            member_host = _extract_first_host(args.admin_uri)
        if not member_host:
            _safe_print("ERROR: could not infer member host. Provide --member-host host:port")
            return 2

        _safe_print(f"Initializing replica set '{rs_name}' with member '{member_host}'...")
        try:
            client.admin.command(
                {
                    "replSetInitiate": {
                        "_id": rs_name,
                        "members": [{"_id": 0, "host": member_host}],
                    }
                }
            )
        except OperationFailure as exc:
            msg = str(exc).lower()
            if "already initialized" not in msg and "already initiated" not in msg:
                if (
                    "not authorized" in msg
                    or "unauthorized" in msg
                    or getattr(exc, "code", None) == 13
                ):
                    _safe_print(
                        "ERROR: Mongo user is not authorized for replSet commands. "
                        "Use an admin user with clusterAdmin/root role."
                    )
                    return 3
                _safe_print(f"ERROR: replSetInitiate failed: {exc}")
                return 4

        if not _wait_for_primary(client, rs_name=rs_name, timeout_seconds=args.timeout_seconds):
            _safe_print("ERROR: replica set was not ready before timeout.")
            return 5
        _safe_print(f"Replica set enabled successfully: {rs_name}")

    app_uri = str(args.app_uri or "").strip() or str(args.admin_uri).strip()
    normalized_app_uri = _ensure_replica_set_uri(app_uri, rs_name)
    db_name = _resolve_db_name(args.db_name, app_uri)

    _safe_print("")
    _safe_print("Normalized application URI:")
    _safe_print(normalized_app_uri)

    if args.write_cloud_config:
        cfg_path = Path("cloud_config.json")
        _update_cloud_config(cfg_path, normalized_app_uri, db_name)
        _safe_print(f"Updated {cfg_path}")

    if args.write_env:
        env_path = Path(".env")
        _update_env_file(env_path, normalized_app_uri, db_name)
        _safe_print(f"Updated {env_path}")

    _safe_print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
