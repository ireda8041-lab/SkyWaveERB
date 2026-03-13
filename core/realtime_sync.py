"""
🔄 نظام المزامنة الفورية (Real-time Sync)
مزامنة فورية بين الأجهزة عبر MongoDB Change Streams

⚡ المميزات:
- مراقبة التغييرات في MongoDB فوراً
- مزامنة البيانات بين الأجهزة في الوقت الحقيقي
- إرسال إشارات لتحديث الواجهة
"""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from PyQt6.QtCore import QObject, pyqtSignal

from core.logger import get_logger

# استيراد دالة الطباعة الآمنة
try:
    from core.safe_print import safe_print
except ImportError:

    def safe_print(msg):
        try:
            print(msg)
        except UnicodeEncodeError:
            pass


# استيراد آمن لـ pymongo
try:
    import pymongo
    from pymongo.errors import PyMongoError

    PYMONGO_AVAILABLE = True
except ImportError:
    pymongo = None

    class PyMongoError(Exception):
        pass

    PYMONGO_AVAILABLE = False

logger = get_logger(__name__)

# المتغير العام لمدير المزامنة الفورية
_REALTIME_MANAGER = None
DEFAULT_CHANGE_STREAM_MAX_AWAIT_MS = 250
DEFAULT_EVENT_DEDUPE_MS = 120
_PROCESS_LOCAL_RS_BOOTSTRAP_ATTEMPTED = False


def _split_mongo_hosts(uri: str) -> list[str]:
    try:
        if not isinstance(uri, str):
            return []
        parts = urlsplit(uri)
        if not parts.netloc:
            return []
        netloc = parts.netloc.split("@")[-1]
        return [h.strip() for h in netloc.split(",") if h.strip()]
    except Exception:
        return []


def is_local_mongo_uri(uri: str) -> bool:
    if not isinstance(uri, str):
        return False
    uri_l = uri.strip().lower()
    if uri_l.startswith("mongodb+srv://"):
        return False
    if not uri_l.startswith("mongodb://"):
        return False
    hosts = _split_mongo_hosts(uri)
    if not hosts:
        return False
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    for host_item in hosts:
        host = host_item
        if host.startswith("[") and "]" in host:
            host = host[1 : host.index("]")]
        else:
            host = host.split(":", 1)[0]
        if host.strip().lower() not in local_hosts:
            return False
    return True


def ensure_replica_set_uri(uri: str, replica_set_name: str = "rs0") -> str:
    """
    Ensure URI contains replicaSet and directConnection=false for local single-node setups.
    Non mongodb:// URIs are returned unchanged.
    """
    try:
        if not isinstance(uri, str) or not uri.strip():
            return uri
        if not uri.lower().startswith("mongodb://"):
            return uri

        rs_name = (replica_set_name or "rs0").strip() or "rs0"
        parts = urlsplit(uri)
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        query_map = dict(query_pairs)
        existing_rs = str(query_map.get("replicaSet") or "").strip()
        if not existing_rs or existing_rs.lower() != rs_name.lower():
            query_map["replicaSet"] = rs_name

        direct_connection = str(query_map.get("directConnection") or "").strip().lower()
        if (not direct_connection) or direct_connection != "false":
            query_map["directConnection"] = "false"

        rebuilt_query = urlencode(list(query_map.items()))
        return urlunsplit((parts.scheme, parts.netloc, parts.path, rebuilt_query, parts.fragment))
    except Exception:
        return uri


def _extract_preferred_member_host(uri: str, hello_payload: dict | None = None) -> str:
    hello_payload = hello_payload or {}
    me_host = str(hello_payload.get("me") or "").strip()
    if me_host:
        return me_host

    hosts = _split_mongo_hosts(uri)
    if not hosts:
        return ""
    first = hosts[0]
    if ":" in first:
        return first
    return f"{first}:27017"


def try_bootstrap_local_replica_set(
    mongo_client,
    uri: str,
    replica_set_name: str = "rs0",
    timeout_seconds: float = 12.0,
) -> tuple[bool, str]:
    """
    Try to initialize a local single-node replica set for Change Streams.
    Returns (success, details).
    """
    if mongo_client is None:
        return False, "Mongo client غير متاح."
    if not is_local_mongo_uri(uri):
        return False, "الاتصال ليس Localhost؛ التفعيل التلقائي متاح فقط للـ Mongo المحلي."

    try:
        admin = mongo_client.admin
        hello = admin.command("hello")
        set_name = str(hello.get("setName") or "").strip()
        if set_name:
            return True, f"Replica Set مفعل بالفعل ({set_name})."

        rs_name = (replica_set_name or "rs0").strip() or "rs0"
        preferred_host = _extract_preferred_member_host(uri, hello)
        if not preferred_host:
            return False, "تعذر تحديد عنوان السيرفر لتهيئة Replica Set."

        try:
            admin.command(
                {
                    "replSetInitiate": {
                        "_id": rs_name,
                        "members": [{"_id": 0, "host": preferred_host}],
                    }
                }
            )
        except Exception as initiate_error:
            error_text = str(initiate_error).lower()
            # Accept already-initialized states.
            if "already initialized" not in error_text and "already initiated" not in error_text:
                if "not running with --replset" in error_text:
                    return (
                        False,
                        "Mongo يعمل بدون replSetName. فعّل replication.replSetName ثم أعد التشغيل.",
                    )
                return False, f"فشل تهيئة Replica Set: {initiate_error}"

        deadline = time.time() + max(3.0, float(timeout_seconds))
        while time.time() < deadline:
            try:
                probe = admin.command("hello")
                probe_set_name = str(probe.get("setName") or "").strip()
                if probe_set_name:
                    return True, f"تم تفعيل Replica Set بنجاح ({probe_set_name})."
            except Exception:
                pass
            time.sleep(0.4)

        return False, "تم إرسال أوامر التهيئة لكن لم تصبح العقدة Replica Set ضمن المهلة."
    except Exception as e:
        return False, f"تعذر تفعيل Replica Set تلقائياً: {e}"


def check_change_stream_support(mongo_db, max_await_ms: int = 100) -> tuple[bool, str]:
    if mongo_db is None:
        return False, "Mongo database غير متاحة."
    try:
        with mongo_db.watch(max_await_time_ms=max_await_ms) as stream:
            try:
                stream.try_next()
            except Exception:
                pass
        return True, "Change Streams مدعومة."
    except Exception as e:
        return False, str(e)


class RealtimeSyncManager(QObject):
    """
    🔄 مدير المزامنة الفورية
    يراقب التغييرات في MongoDB ويزامن البيانات فوراً
    ⚡ محسّن للأداء - يستخدم thread واحد فقط بدلاً من thread لكل collection
    """

    # إشارات
    data_updated = pyqtSignal(str, dict)  # (collection_name, change_data)
    connection_status_changed = pyqtSignal(bool)  # (is_connected)
    sync_completed = pyqtSignal(str)  # (collection_name)
    _emit_pending_requested = pyqtSignal()

    # الجداول المراقبة - تقليل العدد للأداء
    COLLECTIONS = [
        "accounts",
        "clients",
        "services",
        "projects",
        "invoices",
        "payments",
        "expenses",
        "journal_entries",
        "currencies",
        "notifications",
        "tasks",
        "system_settings",
    ]

    def __init__(self, repository, parent=None):
        super().__init__(parent)
        self.repo = repository
        self.is_running = False
        self._shutdown = False
        self._stop_event = threading.Event()
        self._watcher_thread = None  # ⚡ thread واحد فقط
        self._last_sync_time = {}
        self._pending_changes_lock = threading.Lock()
        self._emit_dispatch_queued = False
        self._event_dedupe_ms = DEFAULT_EVENT_DEDUPE_MS
        self._last_collection_event_ms: dict[str, int] = {}
        self._pending_changes = set()  # ⚡ تجميع التغييرات
        self._debounce_timer = None
        self._realtime_enabled = True
        self._realtime_auto_detect = True
        self._change_stream_max_await_ms = DEFAULT_CHANGE_STREAM_MAX_AWAIT_MS
        self._change_stream_supported = None
        self._support_warning_logged = False
        self._local_rs_bootstrap_enabled = True
        self._local_rs_name = "rs0"
        self._local_rs_timeout_seconds = 12.0
        self._local_rs_bootstrap_attempted = bool(_PROCESS_LOCAL_RS_BOOTSTRAP_ATTEMPTED)
        self._local_service_replset_fix_enabled = True
        self._local_service_replset_fix_timeout_seconds = 180.0
        self._local_service_replset_fix_attempted = False
        self._local_service_replset_fix_running = False
        self._local_service_replset_fix_cooldown_seconds = 300.0
        self._last_local_service_replset_fix_attempt_at = 0.0
        self._local_mongo_service_name = (
            str(os.environ.get("SKYWAVE_MONGO_SERVICE_NAME", "MongoDB")).strip() or "MongoDB"
        )
        self._load_runtime_config()
        self._emit_pending_requested.connect(self._emit_pending_changes_slot)

        # تهيئة أوقات المزامنة
        for collection in self.COLLECTIONS:
            self._last_sync_time[collection] = datetime.now()

        logger.info("[RealtimeSync] ✅ تم تهيئة مدير المزامنة الفورية (محسّن)")

    def _load_runtime_config(self):
        try:
            config_path = Path("sync_config.json")
            if not config_path.exists():
                return
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            self._realtime_enabled = bool(cfg.get("realtime_enabled", True))
            self._realtime_auto_detect = bool(cfg.get("realtime_auto_detect", True))
            try:
                self._change_stream_max_await_ms = int(
                    cfg.get(
                        "realtime_change_stream_max_await_ms",
                        DEFAULT_CHANGE_STREAM_MAX_AWAIT_MS,
                    )
                )
            except (TypeError, ValueError):
                self._change_stream_max_await_ms = DEFAULT_CHANGE_STREAM_MAX_AWAIT_MS
            self._change_stream_max_await_ms = max(50, min(5000, self._change_stream_max_await_ms))
            try:
                self._event_dedupe_ms = int(
                    cfg.get("realtime_event_dedupe_ms", DEFAULT_EVENT_DEDUPE_MS)
                )
            except (TypeError, ValueError):
                self._event_dedupe_ms = DEFAULT_EVENT_DEDUPE_MS
            self._event_dedupe_ms = max(0, min(5000, self._event_dedupe_ms))
            self._local_rs_bootstrap_enabled = bool(
                cfg.get("realtime_attempt_local_rs_bootstrap", True)
            )
            rs_name = str(cfg.get("realtime_replica_set_name", "rs0")).strip()
            self._local_rs_name = rs_name or "rs0"
            try:
                timeout_value = float(cfg.get("realtime_local_rs_bootstrap_timeout_s", 12.0))
            except (TypeError, ValueError):
                timeout_value = 12.0
            self._local_rs_timeout_seconds = max(3.0, min(60.0, timeout_value))
            self._local_service_replset_fix_enabled = bool(
                cfg.get("realtime_attempt_service_replset_fix", True)
            )
            try:
                service_fix_timeout = float(
                    cfg.get("realtime_service_replset_fix_timeout_s", 180.0)
                )
            except (TypeError, ValueError):
                service_fix_timeout = 180.0
            self._local_service_replset_fix_timeout_seconds = max(
                20.0, min(600.0, service_fix_timeout)
            )
            try:
                service_fix_cooldown = float(
                    cfg.get("realtime_service_replset_fix_cooldown_s", 300.0)
                )
            except (TypeError, ValueError):
                service_fix_cooldown = 300.0
            self._local_service_replset_fix_cooldown_seconds = max(
                60.0, min(3600.0, service_fix_cooldown)
            )
            mongo_service_name = str(
                cfg.get("realtime_mongo_service_name", self._local_mongo_service_name)
            ).strip()
            if mongo_service_name:
                self._local_mongo_service_name = mongo_service_name
        except Exception as e:
            logger.debug("[RealtimeSync] فشل تحميل الإعدادات: %s", e)

    def _detect_change_stream_support(self) -> bool:
        if self.repo is None or self.repo.mongo_db is None:
            return False
        supported, details = check_change_stream_support(self.repo.mongo_db, max_await_ms=100)
        if supported:
            return True
        e = details
        try:
            if not self._support_warning_logged:
                error_text = str(e).lower()
                expected_not_supported = (
                    "only supported on replica sets" in error_text
                    or "code 40573" in error_text
                    or "location40573" in error_text
                    or "changestream" in error_text
                    and "replica set" in error_text
                )
                if expected_not_supported:
                    logger.info(
                        "[RealtimeSync] Change Streams غير متاحة في بيئة Mongo الحالية - سيتم استخدام Delta Sync"
                    )
                    logger.debug("[RealtimeSync] تفاصيل فحص Change Streams: %s", e)
                else:
                    logger.warning(
                        "[RealtimeSync] فشل فحص Change Streams - fallback إلى Delta Sync: %s",
                        e,
                    )
                self._support_warning_logged = True
            return False
        except Exception:
            return False

    def _get_current_mongo_uri(self) -> str:
        uri = os.environ.get("MONGO_URI") or os.environ.get("MONGODB_URI")
        if uri:
            return str(uri).strip()
        try:
            from core.config import Config

            return str(Config.get_mongo_uri()).strip()
        except Exception:
            return ""

    def _persist_runtime_mongo_uri(self, uri: str) -> None:
        clean_uri = str(uri or "").strip()
        if not clean_uri:
            return
        try:
            os.environ["MONGO_URI"] = clean_uri
        except Exception:
            pass
        try:
            import core.repository as repository_module

            repository_module.MONGO_URI = clean_uri
        except Exception:
            pass
        try:
            from core.config import _persist_cloud_config

            _persist_cloud_config()
        except Exception:
            pass

    @staticmethod
    def _is_windows_platform() -> bool:
        return os.name == "nt"

    def _resolve_local_replset_enabler_script(self) -> Path | None:
        candidates = [
            Path("tools") / "enable_local_replset.ps1",
            Path(__file__).resolve().parent.parent / "tools" / "enable_local_replset.ps1",
        ]
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates.extend(
                [
                    exe_dir / "tools" / "enable_local_replset.ps1",
                    exe_dir / "enable_local_replset.ps1",
                ]
            )

        for candidate in candidates:
            try:
                if candidate.exists():
                    return candidate
            except Exception:
                continue
        return None

    def _run_local_replset_enabler_script(self) -> bool:
        if not self._is_windows_platform():
            return False

        script_path = self._resolve_local_replset_enabler_script()
        if script_path is None:
            logger.info("[RealtimeSync] لم يتم العثور على سكربت تفعيل Replica Set المحلي.")
            return False

        cmd = [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(script_path),
            "-ReplicaSetName",
            self._local_rs_name,
            "-MongoServiceName",
            self._local_mongo_service_name,
        ]
        script_timeout = max(45, min(300, int(self._local_service_replset_fix_timeout_seconds)))
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=script_timeout,
                check=False,
            )
        except Exception as e:
            logger.info("[RealtimeSync] تعذر تشغيل سكربت تفعيل Replica Set: %s", e)
            return False

        output = (str(proc.stdout or "") + "\n" + str(proc.stderr or "")).strip()
        if output:
            logger.info("[RealtimeSync] Local Replica Set script output: %s", output)
        if int(proc.returncode) != 0:
            logger.info("[RealtimeSync] سكربت تفعيل Replica Set أنهى بكود %s", proc.returncode)
            return False
        return True

    def _start_local_service_replset_fix_background(self) -> bool:
        if self._local_service_replset_fix_running:
            return False
        self._local_service_replset_fix_running = True
        self._last_local_service_replset_fix_attempt_at = time.time()

        def _worker():
            try:
                ok = self._run_local_replset_enabler_script()
                if ok:
                    logger.info(
                        "[RealtimeSync] تم تشغيل إصلاح خدمة Mongo في الخلفية. سيتم تفعيل Change Streams تلقائياً بعد اكتمال الإصلاح وإعادة المحاولة."
                    )
                else:
                    logger.info(
                        "[RealtimeSync] فشل تشغيل إصلاح خدمة Mongo تلقائياً. سيستمر النظام على Delta Sync."
                    )
            except Exception as e:
                logger.info("[RealtimeSync] خطأ أثناء إصلاح خدمة Mongo في الخلفية: %s", e)
            finally:
                self._local_service_replset_fix_running = False

        threading.Thread(
            target=_worker,
            daemon=True,
            name="RealtimeSync-LocalReplsetFix",
        ).start()
        return True

    def _wait_for_change_stream_support_after_local_fix(self, normalized_uri: str) -> bool:
        deadline = time.time() + max(20.0, float(self._local_service_replset_fix_timeout_seconds))
        while time.time() < deadline:
            if self._shutdown:
                return False
            if (
                self._reconnect_repository_client(normalized_uri)
                and self._detect_change_stream_support()
            ):
                return True
            time.sleep(2.0)
        return False

    def _try_enable_change_streams_locally(self) -> bool:
        global _PROCESS_LOCAL_RS_BOOTSTRAP_ATTEMPTED

        if (not self._local_rs_bootstrap_enabled) and (not self._local_service_replset_fix_enabled):
            return False

        if self.repo is None or self.repo.mongo_client is None:
            return False

        current_uri = self._get_current_mongo_uri()
        if not current_uri:
            logger.info("[RealtimeSync] لم يتم العثور على MONGO_URI لتفعيل Change Streams تلقائياً")
            return False
        if not is_local_mongo_uri(current_uri):
            logger.info("[RealtimeSync] التفعيل التلقائي للـ Replica Set متاح فقط لـ Mongo المحلي")
            return False

        normalized_uri = ensure_replica_set_uri(current_uri, self._local_rs_name)
        if normalized_uri != current_uri:
            self._persist_runtime_mongo_uri(normalized_uri)
            logger.info(
                "[RealtimeSync] تم تحديث URI المحلي لدعم Replica Set (%s)",
                self._local_rs_name,
            )

        if self._local_rs_bootstrap_enabled and not self._local_rs_bootstrap_attempted:
            self._local_rs_bootstrap_attempted = True
            _PROCESS_LOCAL_RS_BOOTSTRAP_ATTEMPTED = True
            ok, details = try_bootstrap_local_replica_set(
                self.repo.mongo_client,
                normalized_uri,
                replica_set_name=self._local_rs_name,
                timeout_seconds=self._local_rs_timeout_seconds,
            )
            if ok:
                if not self._reconnect_repository_client(normalized_uri):
                    logger.info(
                        "[RealtimeSync] تم تفعيل Replica Set لكن تعذر إعادة فتح اتصال Mongo بالـ URI الجديد."
                    )
                    return False
                logger.info("[RealtimeSync] %s", details)
                return True
            logger.info("[RealtimeSync] تعذر تفعيل Change Streams تلقائياً: %s", details)

        if self._local_service_replset_fix_enabled and self._is_windows_platform():
            now = time.time()
            cooldown = max(60.0, float(self._local_service_replset_fix_cooldown_seconds))
            if (now - self._last_local_service_replset_fix_attempt_at) < cooldown:
                return False
            self._local_service_replset_fix_attempted = True
            if self._start_local_service_replset_fix_background():
                logger.info(
                    "[RealtimeSync] تم إطلاق إصلاح خدمة Mongo بالخلفية بدون حجب واجهة المستخدم. سيستمر Delta Sync مؤقتاً."
                )
                return True
        return False

    def _try_enable_change_streams_for_remote_replica_set(self) -> bool:
        """
        For remote Mongo servers: if the server is already a replica set, normalize URI
        with replicaSet/directConnection and reconnect so Change Streams can work.
        """
        if self.repo is None or self.repo.mongo_client is None:
            return False

        current_uri = self._get_current_mongo_uri()
        if not current_uri:
            return False
        if is_local_mongo_uri(current_uri):
            return False

        try:
            hello = self.repo.mongo_client.admin.command("hello")
        except Exception as e:
            logger.debug("[RealtimeSync] تعذر فحص hello على Mongo البعيد: %s", e)
            return False

        remote_set_name = str(hello.get("setName") or "").strip()
        if not remote_set_name:
            return False

        normalized_uri = ensure_replica_set_uri(current_uri, remote_set_name)
        if normalized_uri == current_uri:
            return False

        self._persist_runtime_mongo_uri(normalized_uri)
        if not self._reconnect_repository_client(normalized_uri):
            logger.info(
                "[RealtimeSync] تم تحديث URI للـ Replica Set البعيد لكن تعذر إعادة الاتصال الفوري."
            )
            return False

        logger.info(
            "[RealtimeSync] تم تحديث URI للاتصال البعيد ليتوافق مع Replica Set (%s)",
            remote_set_name,
        )
        return True

    def _reconnect_repository_client(self, mongo_uri: str) -> bool:
        """Reconnect repository Mongo client using a replica-set-aware URI."""
        if self.repo is None or not mongo_uri or not PYMONGO_AVAILABLE or pymongo is None:
            return False

        try:
            old_client = getattr(self.repo, "mongo_client", None)
            old_db = getattr(self.repo, "mongo_db", None)
            db_name = getattr(old_db, "name", None)
            if not db_name:
                try:
                    from core.config import Config

                    db_name = Config.get_db_name()
                except Exception:
                    db_name = "skywave_erp_db"

            if old_client is not None:
                try:
                    old_client.close()
                except Exception:
                    pass

            new_client = pymongo.MongoClient(
                mongo_uri,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000,
                socketTimeoutMS=30000,
                retryWrites=True,
                retryReads=True,
                maxPoolSize=20,
                minPoolSize=2,
                maxIdleTimeMS=120000,
                waitQueueTimeoutMS=10000,
                appname="SkyWaveERP-Realtime",
            )
            new_client.admin.command("ping")
            self.repo.mongo_client = new_client
            self.repo.mongo_db = new_client[str(db_name)]
            self.repo.online = True
            return True
        except Exception as e:
            logger.debug("[RealtimeSync] فشل إعادة الاتصال بـ Mongo بعد تفعيل Replica Set: %s", e)
            return False

    def _sync_system_settings_from_cloud(self):
        try:
            settings_service = getattr(self.repo, "settings_service", None)
            if settings_service:
                settings_service.sync_settings_from_cloud(self.repo)
            try:
                from core.signals import app_signals

                app_signals.system_changed.emit()
            except Exception:
                pass
        except Exception as e:
            logger.debug("[RealtimeSync] فشل مزامنة system_settings: %s", e)

    def start(self):
        """🚀 بدء المزامنة الفورية"""
        if self.is_running:
            return True

        if not self._realtime_enabled:
            logger.info("[RealtimeSync] المزامنة الفورية معطلة من الإعدادات")
            try:
                from core.signals import app_signals

                app_signals.emit_realtime_sync_status(False)
            except Exception:
                pass
            return False

        if not PYMONGO_AVAILABLE:
            logger.warning("[RealtimeSync] pymongo غير متاح - المزامنة الفورية معطّلة")
            try:
                from core.signals import app_signals

                app_signals.emit_realtime_sync_status(False)
            except Exception:
                pass
            return False

        if not self.repo.online or self.repo.mongo_db is None:
            logger.warning("[RealtimeSync] MongoDB غير متاح حالياً - سيتم إعادة المحاولة تلقائياً")
            try:
                from core.signals import app_signals

                app_signals.emit_realtime_sync_status(False)
            except Exception:
                pass
            return False

        if self._realtime_auto_detect:
            self._change_stream_supported = self._detect_change_stream_support()
            if not self._change_stream_supported and self._try_enable_change_streams_locally():
                self._change_stream_supported = self._detect_change_stream_support()
            if (
                not self._change_stream_supported
                and self._try_enable_change_streams_for_remote_replica_set()
            ):
                self._change_stream_supported = self._detect_change_stream_support()
        elif self._change_stream_supported is None:
            self._change_stream_supported = True

        if not self._change_stream_supported:
            try:
                from core.signals import app_signals

                app_signals.emit_realtime_sync_status(False)
            except Exception:
                pass
            return False

        self._shutdown = False
        self._stop_event.clear()
        self.is_running = True

        # ⚡ بدء thread واحد فقط لمراقبة كل الـ collections
        self._start_unified_watcher()

        logger.info("[RealtimeSync] 🚀 بدء المزامنة الفورية (thread واحد)")
        safe_print("INFO: [RealtimeSync] 🚀 بدء المزامنة الفورية (محسّن)")
        try:
            from core.signals import app_signals

            app_signals.emit_realtime_sync_status(True)
        except Exception:
            pass
        return True

    def stop(self):
        """⏹️ إيقاف المزامنة الفورية"""
        if not self.is_running:
            return

        logger.info("[RealtimeSync] ⏹️ جاري إيقاف المزامنة الفورية...")
        self._shutdown = True
        self._stop_event.set()
        self.is_running = False

        # انتظار انتهاء الـ thread
        try:
            if self._watcher_thread and self._watcher_thread.is_alive():
                self._watcher_thread.join(timeout=0.35)
        except Exception:
            pass

        with self._pending_changes_lock:
            self._pending_changes.clear()
            self._emit_dispatch_queued = False
            self._last_collection_event_ms.clear()
        self._watcher_thread = None
        logger.info("[RealtimeSync] ✅ تم إيقاف المزامنة الفورية")
        try:
            from core.signals import app_signals

            app_signals.emit_realtime_sync_status(False)
        except Exception:
            pass

    def _start_unified_watcher(self):
        """⚡ بدء مراقبة موحدة لكل الـ collections في thread واحد"""

        def watch_all_collections():
            logger.debug("[RealtimeSync] بدء المراقبة الموحدة")
            pipeline = [
                {
                    "$match": {
                        "ns.coll": {"$in": self.COLLECTIONS},
                        "operationType": {"$in": ["insert", "update", "replace", "delete"]},
                    }
                }
            ]

            while not self._stop_event.is_set() and not self._shutdown:
                try:
                    if self.repo.mongo_db is None or self.repo.mongo_client is None:
                        time.sleep(1.0)
                        continue

                    with self.repo.mongo_db.watch(
                        pipeline=pipeline,
                        max_await_time_ms=self._change_stream_max_await_ms,
                    ) as stream:
                        for change in stream:
                            if self._stop_event.is_set() or self._shutdown:
                                break
                            if not isinstance(change, dict):
                                continue

                            namespace = change.get("ns") or {}
                            collection_name = namespace.get("coll")
                            if collection_name not in self.COLLECTIONS:
                                continue

                            if collection_name == "system_settings":
                                self._sync_system_settings_from_cloud()
                                continue

                            self._queue_collection_change(collection_name)

                except PyMongoError as e:
                    if self._shutdown:
                        break
                    error_msg = str(e).lower()
                    if "cannot use mongoclient after close" in error_msg:
                        break
                    if "timed out" not in error_msg:
                        logger.debug("[RealtimeSync] خطأ في stream الموحد: %s", e)
                    time.sleep(0.8)
                except Exception as e:
                    if self._shutdown:
                        break
                    logger.debug("[RealtimeSync] خطأ في المراقبة الموحدة: %s", e)
                    time.sleep(1.5)

            logger.debug("[RealtimeSync] انتهاء المراقبة الموحدة")

        # إنشاء وبدء Thread واحد
        self._watcher_thread = threading.Thread(
            target=watch_all_collections, daemon=True, name="RealtimeSync-Unified"
        )
        self._watcher_thread.start()

    def _queue_collection_change(self, collection_name: str) -> None:
        now_ms = int(time.time() * 1000)
        should_schedule = False
        with self._pending_changes_lock:
            last_seen = self._last_collection_event_ms.get(collection_name, 0)
            if self._event_dedupe_ms > 0 and (now_ms - last_seen) < self._event_dedupe_ms:
                return
            self._last_collection_event_ms[collection_name] = now_ms
            self._pending_changes.add(collection_name)
            if not self._emit_dispatch_queued:
                self._emit_dispatch_queued = True
                should_schedule = True
        if should_schedule:
            self._schedule_emit_changes()

    def _schedule_emit_changes(self):
        """⚡ جدولة إرسال التغييرات المجمعة"""
        try:
            self._emit_pending_requested.emit()
        except Exception:
            pass

    def _emit_pending_changes_slot(self):
        """⚡ إرسال التغييرات المجمعة (يعمل على main thread)"""
        with self._pending_changes_lock:
            if not self._pending_changes:
                self._emit_dispatch_queued = False
                return
            changes = list(self._pending_changes)
            self._pending_changes.clear()
            self._emit_dispatch_queued = False

        for collection_name in changes:
            try:
                self.data_updated.emit(collection_name, {"operation": "change"})
                self.sync_completed.emit(collection_name)
                self._last_sync_time[collection_name] = datetime.now()
            except RuntimeError:
                pass

    def _handle_change(self, collection_name: str, change: dict):
        """معالجة تغيير من MongoDB"""
        if collection_name not in self.COLLECTIONS:
            return
        try:
            if collection_name == "system_settings":
                settings_service = getattr(self.repo, "settings_service", None)
                if settings_service:
                    settings_service.sync_settings_from_cloud(self.repo)
                try:
                    from core.signals import app_signals

                    app_signals.system_changed.emit()
                except Exception:
                    pass
                return
            operation = change.get("operationType", "unknown")
            document = change.get("fullDocument", {})
            document_id = change.get("documentKey", {}).get("_id")

            logger.info("[RealtimeSync] 🔄 %s في %s", operation, collection_name)
            safe_print(f"INFO: [RealtimeSync] 🔄 {operation} في {collection_name}")

            # مزامنة التغيير محلياً
            if operation in ["insert", "update", "replace"]:
                self._sync_document_to_local(collection_name, document)
            elif operation == "delete":
                self._delete_document_from_local(collection_name, str(document_id))

            # إرسال إشارة التحديث
            try:
                self.data_updated.emit(
                    collection_name,
                    {
                        "operation": operation,
                        "document_id": str(document_id) if document_id else None,
                    },
                )
                self.sync_completed.emit(collection_name)
            except RuntimeError:
                pass

            # تحديث وقت المزامنة
            self._last_sync_time[collection_name] = datetime.now()

        except Exception as e:
            logger.debug("[RealtimeSync] خطأ في معالجة التغيير: %s", e)

    def _sync_document_to_local(self, collection_name: str, document: dict):
        """مزامنة مستند من MongoDB إلى SQLite"""
        if collection_name not in self.COLLECTIONS:
            return
        if not document:
            return

        try:
            mongo_id = str(document.get("_id", ""))
            if not mongo_id:
                return

            # تحضير البيانات
            data = self._prepare_document_for_sqlite(document)
            data["_mongo_id"] = mongo_id
            data["sync_status"] = "synced"

            cursor = self.repo.get_cursor()
            try:
                # البحث عن السجل المحلي
                cursor.execute(f"SELECT id FROM {collection_name} WHERE _mongo_id = ?", (mongo_id,))
                existing = cursor.fetchone()

                # الحصول على أعمدة الجدول
                cursor.execute(f"PRAGMA table_info({collection_name})")
                table_columns = {row[1] for row in cursor.fetchall()}

                # تصفية البيانات
                filtered_data = {k: v for k, v in data.items() if k in table_columns}

                if existing:
                    # تحديث
                    local_id = existing[0]
                    set_clause = ", ".join([f"{k}=?" for k in filtered_data.keys()])
                    values = list(filtered_data.values()) + [local_id]
                    cursor.execute(f"UPDATE {collection_name} SET {set_clause} WHERE id=?", values)
                else:
                    # إدراج
                    columns = ", ".join(filtered_data.keys())
                    placeholders = ", ".join(["?" for _ in filtered_data])
                    cursor.execute(
                        f"INSERT INTO {collection_name} ({columns}) VALUES ({placeholders})",
                        list(filtered_data.values()),
                    )

                self.repo.sqlite_conn.commit()
                logger.debug("[RealtimeSync] ✅ تم مزامنة %s/%s", collection_name, mongo_id)

            finally:
                cursor.close()

        except Exception as e:
            logger.debug("[RealtimeSync] خطأ في مزامنة المستند: %s", e)

    def _delete_document_from_local(self, collection_name: str, mongo_id: str):
        """حذف مستند من SQLite"""
        if collection_name not in self.COLLECTIONS:
            return
        if not mongo_id:
            return

        try:
            cursor = self.repo.get_cursor()
            try:
                cursor.execute(f"DELETE FROM {collection_name} WHERE _mongo_id = ?", (mongo_id,))
                self.repo.sqlite_conn.commit()
                logger.debug("[RealtimeSync] 🗑️ تم حذف %s/%s", collection_name, mongo_id)
            finally:
                cursor.close()
        except Exception as e:
            logger.debug("[RealtimeSync] خطأ في حذف المستند: %s", e)

    def _prepare_document_for_sqlite(self, document: dict) -> dict:
        """تحضير مستند MongoDB للحفظ في SQLite"""
        import json

        data = dict(document)
        data.pop("_id", None)
        data.pop("id", None)

        # تحويل التواريخ
        date_fields = [
            "created_at",
            "last_modified",
            "date",
            "issue_date",
            "due_date",
            "start_date",
            "end_date",
        ]
        for field in date_fields:
            if field in data and hasattr(data[field], "isoformat"):
                data[field] = data[field].isoformat()

        # تحويل القوائم والكائنات إلى JSON
        json_fields = ["items", "lines", "data", "milestones"]
        for field in json_fields:
            if field in data and isinstance(data[field], list | dict):
                data[field] = json.dumps(data[field], ensure_ascii=False)

        # التأكد من الحقول المطلوبة
        now = datetime.now().isoformat()
        if not data.get("created_at"):
            data["created_at"] = now
        if not data.get("last_modified"):
            data["last_modified"] = now

        return data

    def is_change_stream_supported(self) -> bool:
        return bool(self._change_stream_supported)


def setup_realtime_sync(repository) -> RealtimeSyncManager | None:
    """
    🚀 إعداد وتشغيل نظام المزامنة الفورية

    Args:
        repository: مخزن البيانات

    Returns:
        مدير المزامنة الفورية أو None إذا فشل
    """
    global _REALTIME_MANAGER

    try:
        if _REALTIME_MANAGER is not None:
            return _REALTIME_MANAGER

        _REALTIME_MANAGER = RealtimeSyncManager(repository)
        started = _REALTIME_MANAGER.start()
        if not started:
            _REALTIME_MANAGER = None
            return None

        logger.info("[RealtimeSync] ✅ تم إعداد نظام المزامنة الفورية")
        return _REALTIME_MANAGER

    except Exception as e:
        logger.warning("[RealtimeSync] فشل إعداد المزامنة الفورية: %s", e)
        return None


def shutdown_realtime_sync():
    """⏹️ إيقاف نظام المزامنة الفورية"""
    global _REALTIME_MANAGER

    try:
        if _REALTIME_MANAGER is not None:
            _REALTIME_MANAGER.stop()
            _REALTIME_MANAGER = None
            logger.info("[RealtimeSync] ✅ تم إيقاف نظام المزامنة الفورية")
    except Exception as e:
        logger.debug("[RealtimeSync] خطأ في إيقاف المزامنة: %s", e)


def get_realtime_manager() -> RealtimeSyncManager | None:
    """الحصول على مدير المزامنة الفورية"""
    return _REALTIME_MANAGER


# للتوافق مع الكود القديم
class RealtimeSync(RealtimeSyncManager):
    """Alias للتوافق مع الكود القديم"""

    pass
