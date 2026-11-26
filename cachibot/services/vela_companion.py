"""Vela companion: register CachiBot with a local Vela and serve its desk widgets.

Vela is a desktop host on this computer. While the CachiBot server runs and a
Vela home directory is present, this service writes a registration file into
``<VELA_DATA_DIR or ~/.vela>/companions/`` and answers three loopback HTTP
routes (status, widgets, actions) behind a per-start bearer token. Vela always
calls CachiBot; CachiBot never calls Vela and never holds a Vela credential.

The declared widgets and actions are constants on purpose: Vela asks the owner
to review them once when connecting, and any later change to them makes the
owner re-review. Summaries, on the other hand, change freely.

Everything is best-effort: any failure here is logged and never prevents the
CachiBot server from starting or running.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from cachibot import __version__
from cachibot.config import Config
from cachibot.services.computer.service import ComputerRequestError

if TYPE_CHECKING:
    from cachibot.api.websocket import ConnectionManager
    from cachibot.services.computer.service import ComputerService

logger = logging.getLogger(__name__)

# --- Stable declarations (owner-reviewed by Vela; never vary per start) -----

COMPANION_ID = "cachibot"
COMPANION_NAME = "CachiBot"
COMPANION_DESCRIPTION = (
    "Your CachiBot bots: pending approvals, running work, and a way to answer from Vela."
)
COMPANION_COLOR = "#22c55e"  # the default accent-500 of the web UI

WIDGETS: tuple[dict[str, str], ...] = (
    {"id": "needs-you", "name": "Needs you", "layout": "list", "size": "m"},
    {"id": "runs", "name": "Runs", "layout": "keyvalue", "size": "s"},
)

ACTIONS: tuple[dict[str, str], ...] = (
    {"id": "approve", "title": "Approve", "confirm": "Approve the waiting request?"},
    {
        "id": "deny",
        "title": "Deny",
        "confirm": "Deny the waiting request? If it is a computer pause, the run stops.",
    },
)

_DECLARED_ACTION_IDS = frozenset(action["id"] for action in ACTIONS)

# --- Protocol limits (see vela-contracts companion-v1) -----------------------

_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$")
_COMPANIONS_FOLDER = "companions"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_MAX_ICON_BYTES = 256 * 1024
_MAX_HEAD_BYTES = 16 * 1024
_MAX_BODY_BYTES = 64 * 1024
_READ_TIMEOUT_SECONDS = 10.0
_WIDGETS_TIMEOUT_SECONDS = 5.0
_ACTION_TIMEOUT_SECONDS = 10.0
_MAX_ROWS = 5
_TEXT_LIMIT = 80
_CHANGED_MESSAGE = "That changed - open CachiBot to review it."
_COMPUTER_APPROVE_MESSAGE = "Approving a computer pause happens in CachiBot."
_MONITOR_INTERVAL_SECONDS = 30.0

#: The owner label used when the companion answers a computer needs-you with
#: the documented "skip" refusal. Only the takeover path would need a real
#: user, and the companion never takes over.
_RESPONDER_ID = "vela"
_RESPONDER_NAME = "Vela companion"


@dataclass
class _ActionableItem:
    """One item the companion can act on right now, with its pinning key."""

    key: str
    kind: str  # "approval" (tool approval) or "computer" (needs-you)
    approval_id: str | None = None
    bot_id: str | None = None
    supports_approve: bool = False


# --- Injectable source helpers (monkeypatched by tests) ----------------------


def _ws_manager() -> ConnectionManager:
    from cachibot.api.websocket import get_ws_manager

    return get_ws_manager()


def _computer_service() -> ComputerService:
    from cachibot.services.computer.service import get_computer_service

    return get_computer_service()


async def _bot_name(bot_id: str) -> str | None:
    try:
        from cachibot.storage.repository import BotRepository

        bot = await BotRepository().get_by_id(bot_id)
        return bot.name if bot is not None else None
    except Exception:
        logger.debug("Could not resolve bot name for %s", bot_id, exc_info=True)
        return None


async def _side_tasks_needs_you() -> list[Any]:
    from cachibot.models.side_task import SideTaskStatus
    from cachibot.storage.side_task_repository import SideTaskRepository

    return await SideTaskRepository().get_by_statuses([SideTaskStatus.NEEDS_YOU])


async def _side_task_counts() -> tuple[int, int]:
    from cachibot.models.side_task import SideTaskStatus
    from cachibot.storage.side_task_repository import SideTaskRepository

    repo = SideTaskRepository()
    running = len(await repo.get_by_statuses([SideTaskStatus.RUNNING]))
    waiting = len(await repo.get_by_statuses([SideTaskStatus.WAITING_FOR_SLOT]))
    return running, waiting


async def _running_executions_count() -> int:
    from cachibot.storage.automations_repository import ExecutionLogRepository

    return len(await ExecutionLogRepository().get_running())


async def _awake_computers_count() -> int:
    from cachibot.models.computer import ComputerState
    from cachibot.storage.computer_repository import ComputerRepository

    return len(await ComputerRepository().list_with_state(ComputerState.AWAKE))


# --- Filesystem helpers -------------------------------------------------------


def _vela_home() -> Path:
    env = os.environ.get("VELA_DATA_DIR")
    if env:
        return Path(env)
    return Path.home() / ".vela"


def _env_disables() -> bool:
    return os.environ.get("CACHIBOT_VELA_COMPANION", "").strip().lower() in ("0", "false", "no")


def _write_atomic(path: Path, payload: bytes) -> None:
    """Write beside the target and rename over it, so Vela never reads half a file."""
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(payload)
        os.replace(temporary, path)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise


def _find_packaged_icon() -> Path | None:
    """The app icon shipped with the package, or None when unavailable."""
    package_dir = Path(__file__).resolve().parent.parent
    candidates = (
        package_dir / "frontend_dist" / "icon.png",  # bundled wheel / PyInstaller
        package_dir.parent / "frontend" / "public" / "icon.png",  # dev repo
    )
    for candidate in candidates:
        try:
            if not candidate.is_file() or candidate.stat().st_size > _MAX_ICON_BYTES:
                continue
            if candidate.read_bytes()[: len(_PNG_MAGIC)] != _PNG_MAGIC:
                continue
            return candidate
        except OSError:
            continue
    return None


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _clip(text: str, limit: int = _TEXT_LIMIT) -> str:
    text = _one_line(text)
    return text if len(text) <= limit else text[: limit - 1] + "…"


class VelaCompanionService:
    """Loopback companion endpoint + registration, owned by the app lifespan.

    A lightweight monitor re-checks every ~30 s so a Vela installed later is
    picked up, and a Vela that disappears or a toggled-off setting tears the
    server and the registration files down again.
    """

    def __init__(self, monitor_interval: float = _MONITOR_INTERVAL_SECONDS) -> None:
        self._monitor_interval = monitor_interval
        self._running = False
        self._enabled = True
        self._monitor_task: asyncio.Task[None] | None = None
        self._server: asyncio.Server | None = None
        self._port: int | None = None
        self._token: str | None = None
        self._registration_path: Path | None = None
        self._icon_path: Path | None = None
        #: The pinning key of the single item the last widget summary offered
        #: buttons for. Actions re-check it before touching anything.
        self._advertised: str | None = None
        self._last_seen_at: datetime | None = None

    # ------------------------------------------------------------------ state

    def is_detected(self) -> bool:
        """A Vela home directory exists. CachiBot never creates it."""
        try:
            return _vela_home().is_dir()
        except OSError:
            return False

    def is_enabled(self) -> bool:
        return self._enabled

    def is_registered(self) -> bool:
        return self._registration_path is not None and self._registration_path.is_file()

    def status_snapshot(self) -> dict[str, Any]:
        """What the settings UI may show. Never exposes token or port."""
        return {
            "detected": self.is_detected(),
            "enabled": self._enabled,
            "registered": self.is_registered(),
            "lastSeenAt": self._last_seen_at.isoformat() if self._last_seen_at else None,
        }

    # -------------------------------------------------------------- lifecycle

    async def start(self) -> None:
        if self._running:
            return
        self._enabled = self._load_enabled()
        self._running = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
        logger.info("Vela companion service started (enabled=%s)", self._enabled)

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        task, self._monitor_task = self._monitor_task, None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await self._stop_server()
        logger.info("Vela companion service stopped")

    async def set_enabled(self, enabled: bool) -> None:
        """Persist the owner's choice and apply it immediately."""
        self._enabled = enabled and not _env_disables()
        try:
            config = Config.load()
            config.vela_companion.enabled = enabled
            config.save_vela_companion_config()
        except Exception:
            logger.warning("Could not persist the Vela companion setting", exc_info=True)
        if self._running:
            await self._sync()

    def _load_enabled(self) -> bool:
        if _env_disables():
            return False
        try:
            return bool(Config.load().vela_companion.enabled) and not _env_disables()
        except Exception:
            logger.debug("Could not load the Vela companion setting", exc_info=True)
            return not _env_disables()

    async def _monitor_loop(self) -> None:
        while self._running:
            try:
                await self._sync()
            except Exception:
                logger.debug("Vela companion sync failed", exc_info=True)
            await asyncio.sleep(self._monitor_interval)

    async def _sync(self) -> None:
        if self.is_detected() and self._enabled:
            if self._server is None:
                await self._start_server()
        elif self._server is not None:
            await self._stop_server()

    # ------------------------------------------------------ server + registration

    async def _start_server(self) -> None:
        if not _VERSION_RE.fullmatch(__version__):
            logger.debug(
                "Vela companion not registering: version %r fails the schema pattern", __version__
            )
            return
        try:
            folder = _vela_home() / _COMPANIONS_FOLDER
            folder.mkdir(parents=True, exist_ok=True)
            server = await asyncio.start_server(self._handle_connection, "127.0.0.1", 0)
            self._server = server
            sockname = server.sockets[0].getsockname()
            self._port = int(sockname[1])
            self._token = secrets.token_urlsafe(48)
            self._last_seen_at = None
            self._advertised = None
            self._write_icon(folder)
            self._write_registration(folder)
            logger.info("Vela companion registered (endpoint http://127.0.0.1:%d)", self._port)
        except Exception:
            logger.warning("Vela companion could not register", exc_info=True)
            await self._discard_server()

    async def _discard_server(self) -> None:
        server, self._server = self._server, None
        self._port = None
        self._token = None
        self._registration_path = None
        self._icon_path = None
        self._advertised = None
        if server is not None:
            server.close()
            await server.wait_closed()

    async def _stop_server(self) -> None:
        server = self._server
        token = self._token
        registration = self._registration_path
        icon = self._icon_path
        await self._discard_server()
        if server is not None:
            logger.info("Vela companion unregistered")
        self._remove_registration(registration, token)
        if icon is not None:
            try:
                icon.unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not remove the companion icon", exc_info=True)

    def _write_icon(self, folder: Path) -> None:
        """Copy the packaged icon next to the registration, when one exists."""
        self._icon_path = None
        source = _find_packaged_icon()
        if source is None:
            logger.debug("No packaged PNG icon found; registering without an icon")
            return
        try:
            target = folder / f"{COMPANION_ID}.png"
            _write_atomic(target, source.read_bytes())
            self._icon_path = target
        except OSError:
            logger.debug("Could not write the companion icon", exc_info=True)

    def _write_registration(self, folder: Path) -> None:
        registration: dict[str, Any] = {
            "companion": 1,
            "id": COMPANION_ID,
            "name": COMPANION_NAME,
            "description": COMPANION_DESCRIPTION,
            "version": __version__,
            "color": COMPANION_COLOR,
            "endpoint": f"http://127.0.0.1:{self._port}",
            "token": self._token,
            "pid": os.getpid(),
            "widgets": [dict(widget) for widget in WIDGETS],
            "actions": [dict(action) for action in ACTIONS],
        }
        if self._icon_path is not None:
            registration["icon"] = f"{COMPANION_ID}.png"
        # CachiBot runs under Python / Electron: no executable for Vela to launch.
        payload = json.dumps(registration, indent=2).encode("utf-8")
        target = folder / f"{COMPANION_ID}.json"
        _write_atomic(target, payload)
        self._registration_path = target

    @staticmethod
    def _remove_registration(path: Path | None, token: str | None) -> None:
        """Own-file safety: only delete the registration if it still carries
        OUR token — two CachiBot servers can share the companions folder."""
        if path is None or token is None:
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict) or not isinstance(data.get("token"), str):
            return
        if not hmac.compare_digest(data["token"], token):
            return
        try:
            path.unlink(missing_ok=True)
        except OSError:
            logger.debug("Could not remove the companion registration", exc_info=True)

    # ------------------------------------------------------------- HTTP surface

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        try:
            peer = writer.get_extra_info("peername")
            host = peer[0] if isinstance(peer, tuple) and peer else None
            if host not in ("127.0.0.1", "::1", "localhost"):
                return
            request = await asyncio.wait_for(self._read_request(reader), _READ_TIMEOUT_SECONDS)
            if request is None:
                await self._respond(writer, 400, {"error": "Bad request."})
                return
            method, path, authorization = request
            expected = f"Bearer {self._token or ''}"
            given = authorization.encode("utf-8") if authorization is not None else b""
            if not hmac.compare_digest(given, expected.encode("utf-8")):
                await self._respond(writer, 401, {"error": "Not allowed."})
                return
            self._last_seen_at = datetime.now(timezone.utc)
            status, body = await self._route(method, path)
            await self._respond(writer, status, body)
        except (asyncio.TimeoutError, ConnectionError, OSError):
            pass
        except Exception:
            logger.debug("Vela companion request failed", exc_info=True)
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionError, OSError):
                pass

    async def _read_request(
        self, reader: asyncio.StreamReader
    ) -> tuple[str, str, str | None] | None:
        buffer = b""
        while b"\r\n\r\n" not in buffer:
            chunk = await reader.read(4096)
            if not chunk:
                return None
            buffer += chunk
            if len(buffer) > _MAX_HEAD_BYTES:
                return None
        head, _, rest = buffer.partition(b"\r\n\r\n")
        lines = head.decode("iso-8859-1").split("\r\n")
        parts = lines[0].split(" ") if lines else []
        method = parts[0] if parts else ""
        path = parts[1].split("?")[0] if len(parts) > 1 else ""
        authorization: str | None = None
        length = 0
        for line in lines[1:]:
            name, separator, value = line.partition(":")
            if not separator:
                continue
            key = name.strip().lower()
            if key == "authorization":
                authorization = value.strip()
            elif key == "content-length":
                try:
                    length = int(value.strip())
                except ValueError:
                    return None
        if length > _MAX_BODY_BYTES:
            return None
        # The body is read and dropped: every route here takes `{}` or nothing.
        have = len(rest)
        while have < length:
            chunk = await reader.read(min(4096, length - have))
            if not chunk:
                break
            have += len(chunk)
        return method, path, authorization

    async def _route(self, method: str, path: str) -> tuple[int, dict[str, Any]]:
        if method == "GET" and path == "/vela/v1/status":
            return 200, {"id": COMPANION_ID}
        if method == "GET" and path == "/vela/v1/widgets":
            try:
                widgets = await asyncio.wait_for(self._build_widgets(), _WIDGETS_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                return 503, {"error": "Widgets took too long."}
            return 200, {"widgets": widgets}
        if method == "POST" and path.startswith("/vela/v1/actions/"):
            action_id = path[len("/vela/v1/actions/") :]
            if action_id not in _DECLARED_ACTION_IDS:
                return 404, {"error": "Unknown action."}
            try:
                return await asyncio.wait_for(self._run_action(action_id), _ACTION_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                return 504, {"error": "That took too long."}
        return 404, {"error": "Not found."}

    _REASONS = {
        200: "OK",
        400: "Bad Request",
        401: "Unauthorized",
        404: "Not Found",
        409: "Conflict",
        503: "Service Unavailable",
        504: "Gateway Timeout",
    }

    async def _respond(
        self, writer: asyncio.StreamWriter, status: int, payload: dict[str, Any]
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        reason = self._REASONS.get(status, "Error")
        head = (
            f"HTTP/1.1 {status} {reason}\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Cache-Control: no-store\r\n"
            "Connection: close\r\n"
            "\r\n"
        )
        writer.write(head.encode("ascii") + body)
        await writer.drain()

    # ------------------------------------------------------------------ widgets

    async def _build_widgets(self) -> dict[str, Any]:
        return {
            "needs-you": await self._build_needs_you_widget(),
            "runs": await self._build_runs_widget(),
        }

    async def _build_needs_you_widget(self) -> dict[str, Any]:
        rows, count = await self._needs_you_rows()
        if count == 0:
            self._advertised = None
            return {"rows": [], "caption": "Nothing needs you", "attention": False}
        summary: dict[str, Any] = {
            "rows": rows,
            "attention": True,
            "badge": str(count) if count <= 99 else "99+",
        }
        actionable = self._collect_actionable()
        # Buttons only when exactly one item is actionable right now, and only
        # for what that item supports (a computer pause has no approve path).
        if len(actionable) == 1:
            item = actionable[0]
            if item.supports_approve:
                summary["actions"] = [
                    {"action": "approve", "label": "Approve"},
                    {"action": "deny", "label": "Deny"},
                ]
            else:
                summary["actions"] = [{"action": "deny", "label": "Deny"}]
            self._advertised = item.key
        else:
            self._advertised = None
        return summary

    async def _needs_you_rows(self) -> tuple[list[dict[str, str]], int]:
        """Display rows plus the true total. Every source is real and optional:
        a source that errors is skipped, never faked."""
        rows: list[dict[str, str]] = []
        count = 0

        try:
            for info in _ws_manager().list_pending_approvals():
                count += 1
                if len(rows) >= _MAX_ROWS:
                    continue
                bot_label = await self._bot_label(info.get("botId"))
                tool = _one_line(str(info.get("tool") or "tool"))
                action = _one_line(str(info.get("action") or "wants your approval"))
                rows.append(
                    {
                        "label": _clip(bot_label or "Chat approval"),
                        "detail": _clip(f"{tool}: {action}"),
                    }
                )
        except Exception:
            logger.debug("needs-you widget: skipping approvals source", exc_info=True)

        try:
            for item in _computer_service().list_needs_you():
                count += 1
                if len(rows) >= _MAX_ROWS:
                    continue
                rows.append(
                    {
                        "label": _clip(await self._bot_label(item.bot_id) or "Bot computer"),
                        "detail": _clip(item.reason),
                    }
                )
        except Exception:
            logger.debug("needs-you widget: skipping computer source", exc_info=True)

        try:
            for task in await _side_tasks_needs_you():
                count += 1
                if len(rows) >= _MAX_ROWS:
                    continue
                reason = _one_line(str(getattr(task, "needs_you_reason", "") or ""))
                detail = f"side task: {reason}" if reason else "side task needs you"
                rows.append(
                    {
                        "label": _clip(str(getattr(task, "title", "") or "Side task")),
                        "detail": _clip(detail),
                    }
                )
        except Exception:
            logger.debug("needs-you widget: skipping side tasks source", exc_info=True)

        return rows, count

    async def _build_runs_widget(self) -> dict[str, Any]:
        """Real run status only; a source that errors is left out entirely."""
        rows: list[dict[str, str]] = []
        active = 0
        try:
            running, waiting = await _side_task_counts()
            rows.append({"label": "Side tasks running", "detail": str(running)})
            rows.append({"label": "Side tasks waiting", "detail": str(waiting)})
            active += running
        except Exception:
            logger.debug("runs widget: skipping side task counts", exc_info=True)
        try:
            executions = await _running_executions_count()
            rows.append({"label": "Runs", "detail": str(executions)})
            active += executions
        except Exception:
            logger.debug("runs widget: skipping execution counts", exc_info=True)
        try:
            awake = await _awake_computers_count()
            rows.append({"label": "Awake computers", "detail": str(awake)})
        except Exception:
            logger.debug("runs widget: skipping computer counts", exc_info=True)
        caption = f"{active} running" if active else "Nothing is running right now"
        return {"rows": rows, "caption": caption}

    async def _bot_label(self, bot_id: Any) -> str | None:
        if not isinstance(bot_id, str) or not bot_id:
            return None
        return await _bot_name(bot_id)

    # ------------------------------------------------------------------ actions

    def _collect_actionable(self) -> list[_ActionableItem]:
        items: list[_ActionableItem] = []
        try:
            for info in _ws_manager().list_pending_approvals():
                approval_id = info.get("id")
                if not isinstance(approval_id, str) or not approval_id:
                    continue
                bot_id = info.get("botId")
                items.append(
                    _ActionableItem(
                        key=f"approval:{approval_id}",
                        kind="approval",
                        approval_id=approval_id,
                        bot_id=bot_id if isinstance(bot_id, str) else None,
                        supports_approve=True,
                    )
                )
        except Exception:
            logger.debug("actionable items: skipping approvals source", exc_info=True)
        try:
            for entry in _computer_service().list_needs_you():
                reference = entry.request_id or entry.run_id or "needs-you"
                items.append(
                    _ActionableItem(
                        key=f"computer:{entry.bot_id}:{reference}",
                        kind="computer",
                        bot_id=entry.bot_id,
                    )
                )
        except Exception:
            logger.debug("actionable items: skipping computer source", exc_info=True)
        return items

    async def _run_action(self, action_id: str) -> tuple[int, dict[str, Any]]:
        # Pinning: re-read what is actionable right now and require it to be
        # exactly the item the widget summary advertised when it drew the
        # buttons. Never approve "the oldest", never "all".
        actionable = self._collect_actionable()
        if len(actionable) != 1:
            return 409, {"error": _CHANGED_MESSAGE}
        item = actionable[0]
        if self._advertised is None or item.key != self._advertised:
            return 409, {"error": _CHANGED_MESSAGE}
        if action_id == "approve":
            if not item.supports_approve:
                return 409, {"error": _COMPUTER_APPROVE_MESSAGE}
            if not _ws_manager().resolve_approval(item.approval_id or "", True):
                return 409, {"error": _CHANGED_MESSAGE}
            self._advertised = None
            return 200, {"message": "Approved the waiting request."}
        if item.kind == "computer":
            try:
                await _computer_service().respond_needs_you(
                    item.bot_id or "", _RESPONDER_ID, _RESPONDER_NAME, "skip"
                )
            except ComputerRequestError as exc:
                status = exc.status_code if exc.status_code < 500 else 502
                return status, {"error": exc.detail}
            except Exception:
                logger.warning("Computer needs-you deny failed", exc_info=True)
                return 502, {"error": "Could not reach the computer."}
            self._advertised = None
            return 200, {"message": "Denied — the run stops."}
        if not _ws_manager().resolve_approval(item.approval_id or "", False):
            return 409, {"error": _CHANGED_MESSAGE}
        self._advertised = None
        return 200, {"message": "Denied the waiting request."}


_vela_companion_service: VelaCompanionService | None = None


def get_vela_companion_service() -> VelaCompanionService:
    """Get the Vela companion service singleton."""
    global _vela_companion_service
    if _vela_companion_service is None:
        _vela_companion_service = VelaCompanionService()
    return _vela_companion_service
