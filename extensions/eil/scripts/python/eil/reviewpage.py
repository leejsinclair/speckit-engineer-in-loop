"""``eil review serve``: the browser review page (004 research D-60, D-61, D-66, D-68; contracts/cli.md).

One process serves one story to one person, one request at a time (``http.server.HTTPServer``, not
the threading variant), on loopback unless a host is given. Every request is checked before it is
routed:

* the ``Host`` header names ``127.0.0.1``, ``localhost``, the bound host, or ``--public-name``;
* the per-process token is the ``?t=`` of ``GET /`` and ``GET /doc/<stage>``, and the ``X-EIL-Token``
  header of everything else;
* every ``POST`` also carries the page's own ``Origin`` and a JSON body.

A failed check is ``403`` and writes nothing. Only the routes in ``ROUTES`` are served; no static file
is read: the page's CSS and script are constants in ``pagerender``. Every record is written by
``reviews.answer``, the function the command line calls, under the record lock (D-63, D-67).
"""

from __future__ import annotations

import hmac
import json
import re
import secrets
import socket
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import pagerender
from .identity import Config, is_ai_actor
from .package import STAGES, Package
from .results import EilExit, Refusal, refuse

LOOPBACK = ("127.0.0.1", "localhost", "::1")
FIRST_PORT, LAST_PORT = 8100, 8199
MAX_BODY = 1024 * 1024
DOC_PATH = re.compile(r"^/doc/(?P<stage>[a-z-]+)$")


class PageServer(HTTPServer):
    """The page's process state (data-model "Review page process"). Nothing here is a record."""

    def __init__(
        self,
        address: tuple[str, int],
        story_dir: Path,
        name: str,
        *,
        public_name: str | None,
        idle_minutes: float,
        config: Config,
    ) -> None:
        self.stopped = threading.Event()  # set when the idle stop ended the server
        self._closed = threading.Event()
        self._idle: threading.Thread | None = None
        super().__init__(address, Handler)
        self.story_dir = Path(story_dir)
        self.token = secrets.token_urlsafe(32)
        self.name = name
        self.bound_host = address[0]
        self.public_name = public_name if public_name and not _loopback(address[0]) else None
        self.idle_seconds = float(idle_minutes) * 60
        self.config = config
        self.last_use = time.monotonic()

    @property
    def port(self) -> int:
        return int(self.server_address[1])

    @property
    def display_host(self) -> str:
        if self.public_name:
            return self.public_name
        return "127.0.0.1" if self.bound_host in ("0.0.0.0", "::", "") else self.bound_host

    @property
    def address(self) -> str:
        """The address the agent gives the person, token included."""
        return f"http://{self.display_host}:{self.port}/?t={self.token}"

    def allowed_hosts(self) -> set[str]:
        hosts = {"127.0.0.1", "localhost", self.bound_host.lower()}
        if self.public_name:
            hosts.add(self.public_name.lower())
        return hosts

    def used(self) -> None:
        self.last_use = time.monotonic()

    def serve_forever(self, poll_interval: float = 0.5) -> None:
        """Serve, with the idle stop running beside it (D-66): ``last_use`` is set by every request but
        ``GET /state``; when it is older than the idle period the server shuts down."""
        if self._idle is None:
            self._idle = threading.Thread(target=self._watch_idle, daemon=True)
            self._idle.start()
        super().serve_forever(poll_interval)

    def server_close(self) -> None:
        self._closed.set()
        super().server_close()

    def _watch_idle(self) -> None:
        step = max(0.02, min(5.0, self.idle_seconds / 4))
        while not self.stopped.is_set() and not self._closed.is_set():
            time.sleep(step)
            if time.monotonic() - self.last_use > self.idle_seconds:
                self.stopped.set()
                self.shutdown()
                return


def _loopback(host: str) -> bool:
    return host in LOOPBACK or host.startswith("127.")


def _hostname(header: str | None) -> str | None:
    """The host part of a ``Host`` header, lower-cased; ``None`` when there is none."""
    if not header or not header.strip():
        return None
    host = header.strip().lower()
    if host.startswith("["):
        return host[1 : host.find("]")] if "]" in host else None
    return host.rsplit(":", 1)[0] if ":" in host else host


OPEN_THE_ADDRESS = (
    "This review page opens only from the address the agent gave you, which carries a one-time key. "
    "Open the address the agent gave you, including its ?t= part."
)


class Handler(BaseHTTPRequestHandler):
    server: PageServer
    protocol_version = "HTTP/1.0"
    server_version = "eil-review"
    sys_version = ""

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - the base class's name
        return None

    def __getattr__(self, name: str) -> Any:
        if name.startswith("do_"):
            return self._not_allowed
        raise AttributeError(name)

    # ---- responses

    def end_headers(self) -> None:
        nonce = self.__dict__.setdefault("nonce", secrets.token_urlsafe(16))
        origin = pagerender.script_origin(self.server.config.diagram_script)
        self.send_header("Content-Security-Policy", pagerender.csp(nonce, origin))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _reply(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(data)

    def _json(self, status: int, payload: Any) -> None:
        self._reply(status, json.dumps(payload, ensure_ascii=False), "application/json; charset=utf-8")

    def _message(self, status: int, text: str) -> None:
        self._reply(status, pagerender.message_page(text, self.nonce))

    def _not_allowed(self) -> None:
        self.__dict__["nonce"] = secrets.token_urlsafe(16)
        self.send_response(405)
        self.send_header("Allow", "GET, POST")
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ---- dispatch

    def do_GET(self) -> None:  # noqa: N802 - the base class's name
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        self.__dict__["nonce"] = secrets.token_urlsafe(16)
        try:
            url = urlsplit(self.path)
            if _hostname(self.headers.get("Host")) not in self.server.allowed_hosts():
                return self._message(403, "This page answers only at the address the agent gave you.")
            path = url.path
            query = parse_qs(url.query)
            page_route = method == "GET" and (path == "/" or DOC_PATH.match(path) is not None)
            given = (query.get("t") or [""])[0] if page_route else self.headers.get("X-EIL-Token", "")
            if not given or not hmac.compare_digest(given.encode("utf-8"), self.server.token.encode("utf-8")):
                return self._message(403, OPEN_THE_ADDRESS)
            if not (method == "GET" and path == "/state"):
                self.server.used()
            if method == "POST":
                return self._post(path)
            if path == "/":
                return self._reply(200, self._page())
            found = DOC_PATH.match(path)
            if found:
                return self._doc(found["stage"])
            if path == "/state":
                return self._json(200, self._state())
            return self._message(404, "Nothing is served here.")
        except EilExit as exc:
            return self._json(200, exc.payload)
        except Exception as exc:  # noqa: BLE001 - the page reports, it never crashes the server
            return self._json(500, {"ok": False, "error": f"{type(exc).__name__}: {exc}"})

    def _post(self, path: str) -> None:
        origin = f"http://{self.headers.get('Host', '')}"
        if self.headers.get("Origin") != origin:
            return self._message(403, "A change must come from the page itself.")
        if (self.headers.get("Content-Type") or "").split(";")[0].strip().lower() != "application/json":
            return self._message(403, "A change must be sent as JSON from the page.")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            return self._json(413, {"ok": False, "error": "the request is too large"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "null")
        except (UnicodeDecodeError, ValueError):
            body = None
        if not isinstance(body, dict):
            return self._json(400, {"ok": False, "error": "the request body must be a JSON object"})
        route = POST_ROUTES.get(path)
        if route is None:
            return self._message(404, "Nothing is served here.")
        return self._json(200, route(self, body))

    # ---- what each route shows

    def package(self) -> Package:
        """The story as it is on disk now: loaded fresh for every request (no cached package)."""
        return Package(self.server.story_dir)

    def _page(self) -> str:
        return pagerender.review_page(self.package(), self.server, self.nonce)

    def _doc(self, stage: str) -> None:
        package = self.package()
        if stage not in STAGES or not package.exists(stage):
            return self._message(404, "There is no such document in this story.")
        return self._reply(200, pagerender.document_page(package, stage, self.server, self.nonce))

    def _state(self) -> dict[str, Any]:
        return pagerender.page_state(self.package(), self.server.config)


Route = Callable[[Handler, dict[str, Any]], dict[str, Any]]


def _text(body: dict[str, Any], name: str) -> str | None:
    value = body.get(name)
    return value if isinstance(value, str) else None


def _write(
    handler: Handler, stage: Any, kind: Any, call: Callable[[Package], dict[str, Any]], any_kind: bool = False
) -> dict[str, Any]:
    """One page write: under the record lock, on the story as it is on disk now, for the current
    review only (``not-current``), with the overview regenerated as a command-line write does."""
    from .blockstatus import persist_adoption
    from .recordfile import record_lock
    from .reviews import current_review

    server = handler.server
    with record_lock(server.story_dir):
        package = Package(server.story_dir)
        if package.record_file().error is None:
            found = current_review(package, server.config.one_at_a_time_max)
            if found["stage"] is None or stage != found["stage"] or (not any_kind and kind != found["kind"]):
                showing = f"{found['stage']}/{found['kind']}" if found["stage"] else "no review"
                raise refuse(
                    Refusal(
                        "not-current",
                        f"this page answered {stage}/{kind}, but the current review is {showing}; nothing was stored",
                        "Reload the page",
                    )
                )
            persist_adoption(package)
            package = Package(server.story_dir)
        result = call(package)
        _regenerate_overview(Package(server.story_dir))
    return {**result, "state": pagerender.page_state(Package(server.story_dir), server.config)}


def _regenerate_overview(package: Package) -> None:
    from . import overview
    from .templates import load_template

    try:
        overview.write(package, load_template(package.project_root or package.root, "s00-readme-template"))
    except EilExit:
        pass  # no preset templates here: the next command-line write regenerates it


def _answer(handler: Handler, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /answer``: one entry's answer, stored by ``reviews.answer`` as a chat answer is (D-63)."""
    from .reviews import DISPOSITIONS, answer

    entry, disposition = _text(body, "entry"), _text(body, "disposition")
    if not entry or disposition not in DISPOSITIONS:
        return {"ok": False, "error": "an answer names an entry and accept, except or question"}
    server = handler.server
    stage, kind = body.get("stage"), body.get("kind")
    return _write(
        handler, stage, kind,
        lambda package: answer(
            package, server.config, str(stage), str(kind), digest=None, by=server.name, reply="", entry=entry,
            disposition=disposition, threshold=server.config.one_at_a_time_max, shown=_text(body, "shown"), via="page",
            asked=_text(body, "question"), comment=_text(body, "comment"),
        ),
    )  # fmt: skip


def _name(handler: Handler, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /name``: who is answering, in memory only; never the AI (determinism 60)."""
    name = " ".join((_text(body, "name") or "").split())
    if not name:
        return {"ok": False, "error": "a name is needed"}
    if is_ai_actor(name):
        raise refuse(
            Refusal(
                "ai-approval",
                f"{name!r} is the AI; the page answers as a person",
                "Give the person's own name",
            )
        )
    handler.server.name = name
    return {"ok": True, "name": name}


def _reopen(handler: Handler, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /reopen``: a comment on a settled block of the current review's stage reopens it (D-65)."""
    from .reviews import answer

    key = _text(body, "key")
    if not key:
        return {"ok": False, "error": "a comment names the block it is on"}
    server = handler.server
    stage = body.get("stage")
    return _write(
        handler, stage, None,
        lambda package: answer(
            package, server.config, str(stage), "inferred", digest=None, by=server.name, reply="", reopen=[key],
            threshold=server.config.one_at_a_time_max, shown=_text(body, "shown"), via="page", comment=_text(body, "comment"),
        ),
        any_kind=True,
    )  # fmt: skip


def _section(handler: Handler, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /section``: accept the unanswered entries of one section together (D-70)."""
    from .reviews import answer

    section = _text(body, "section")
    if not section:
        return {"ok": False, "error": "name the section to accept"}
    server = handler.server
    stage, kind = body.get("stage"), body.get("kind")
    shown = body.get("shown")
    shown_entries = (
        {str(key): value for key, value in shown.items() if isinstance(value, str)}
        if isinstance(shown, dict)
        else None
    )
    return _write(
        handler, stage, kind,
        lambda package: answer(
            package, server.config, str(stage), str(kind), digest=None, by=server.name, reply="", rest=True,
            section=section, threshold=server.config.one_at_a_time_max, shown=shown_entries, via="page",
        ),
    )  # fmt: skip


def _stop(handler: Handler, body: dict[str, Any]) -> dict[str, Any]:
    """``POST /stop``: authenticated local lifecycle control; never relies on a recorded PID."""
    threading.Thread(target=handler.server.shutdown, daemon=True).start()
    return {"ok": True, "stopped": True}


POST_ROUTES: dict[str, Route] = {
    "/answer": _answer,
    "/name": _name,
    "/reopen": _reopen,
    "/section": _section,
    "/stop": _stop,
}


# ---- starting the server


def _first_free(host: str) -> int:
    for port in range(FIRST_PORT, LAST_PORT + 1):
        with socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET) as probe:
            try:
                probe.bind((host, port))
            except OSError:
                continue
            return port
    raise refuse(
        Refusal(
            "port-unavailable",
            f"no free port from {FIRST_PORT} to {LAST_PORT} on {host}",
            "Pass a free port with --port, or stop another page",
        )
    )


def make_server(
    story_dir: Path,
    by: str,
    *,
    host: str = "127.0.0.1",
    port: int | None = None,
    public_name: str | None = None,
    idle_minutes: float | None = None,
    config: Config | None = None,
) -> PageServer:
    """Bind the page for ``story_dir``, answering as ``by``. ``port=None`` takes the first free port
    from 8100; ``0`` lets the system choose. Refuses ``ai-approval`` and ``port-unavailable``."""
    if not by.strip() or is_ai_actor(by):
        raise refuse(
            Refusal(
                "ai-approval",
                f"{by!r} is the AI; the page answers as a person",
                "Pass the person's name with --by",
            )
        )
    if config is None:
        from .identity import load_config

        config = load_config(Package(story_dir).project_root or Path(story_dir))
    idle = config.page_idle_minutes if idle_minutes is None else idle_minutes
    chosen = _first_free(host) if port is None else port
    server_class = _server_class(host)
    try:
        server = server_class(
            (host, chosen),
            Path(story_dir),
            by.strip(),
            public_name=public_name,
            idle_minutes=idle,
            config=config,
        )
    except OSError as exc:
        raise refuse(
            Refusal(
                "port-unavailable",
                f"cannot listen on {host}:{chosen}: {exc.strerror or exc}",
                "Pass a free port with --port",
            )
        ) from exc
    return server


def _server_class(host: str) -> type[PageServer]:
    if ":" in host:

        class V6(PageServer):
            address_family = socket.AF_INET6

        return V6
    return PageServer


# ---- the runtime file, and serve, status and stop (D-66)


def runtime_path(package: Package) -> Path:
    """``<tempdir>/eil-review-<sha256(project root)[:12]>-<story>.json``: outside the project, so starting
    the page changes nothing in it, and removing the extension leaves only the records (FR-023)."""
    import hashlib
    import tempfile

    root = (package.project_root or package.root).resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"eil-review-{digest}-{package.root.name}.json"


def _read_runtime(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _runtime_request(data: dict[str, Any], path: str, *, post: bool = False) -> dict[str, Any] | None:
    """Call a runtime's token-protected endpoint, proving the record still names this page process."""
    from urllib.request import Request, urlopen

    address = data.get("address")
    if not isinstance(address, str):
        return None
    parsed = urlsplit(address)
    token = (parse_qs(parsed.query).get("t") or [""])[0]
    if parsed.scheme != "http" or not parsed.netloc or not token:
        return None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    headers = {"X-EIL-Token": token}
    body = None
    if post:
        headers.update({"Content-Type": "application/json", "Origin": origin})
        body = b"{}"
    try:
        with urlopen(Request(origin + path, data=body, headers=headers), timeout=1.0) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return result if isinstance(result, dict) else None


def status(package: Package) -> dict[str, Any]:
    """``review serve --status``: verify the runtime through its authenticated state endpoint."""
    path = runtime_path(package)
    data = _read_runtime(path)
    if data is None:
        path.unlink(missing_ok=True)
        return {
            "ok": True,
            "running": False,
            "address": None,
            "pid": None,
            "started_at": None,
            "text": "No review page is running for this story.",
        }
    pid = int(data.get("pid") or 0)
    if _runtime_request(data, "/state") is None:
        path.unlink(missing_ok=True)
        return {
            "ok": True,
            "running": False,
            "address": None,
            "pid": None,
            "started_at": None,
            "text": "No review page is running for this story.",
        }
    return {
        "ok": True, "running": True, "address": data.get("address"), "pid": pid, "started_at": data.get("started_at"),
        "text": f"The review page is running at {data.get('address')}",
    }  # fmt: skip


def stop(package: Package, wait: float = 5.0) -> dict[str, Any]:
    """``review serve --stop``: authenticate to the page and ask it to stop. Stored answers stay."""
    path = runtime_path(package)
    data = _read_runtime(path)
    if data is None or _runtime_request(data, "/state") is None:
        path.unlink(missing_ok=True)
        return {"ok": True, "stopped": False, "text": "No review page was running for this story."}
    pid = int(data.get("pid") or 0)
    if _runtime_request(data, "/stop", post=True) is None:
        path.unlink(missing_ok=True)
        return {"ok": True, "stopped": False, "text": "No review page was running for this story."}
    deadline = time.monotonic() + wait
    while path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    path.unlink(missing_ok=True)
    return {
        "ok": True,
        "stopped": True,
        "pid": pid,
        "text": "Stopped the review page. Every answer given on it is stored.",
    }


def serve(
    story_dir: Path,
    by: str,
    *,
    emit: Callable[[dict[str, Any]], None],
    host: str = "127.0.0.1",
    port: int | None = None,
    public_name: str | None = None,
    idle_minutes: float | None = None,
    config: Config | None = None,
) -> dict[str, Any]:
    """Start the page and serve until it is stopped or idle. ``emit`` prints the one JSON line with the
    address as soon as the page listens. Refuses ``page-running``, ``ai-approval``, ``port-unavailable``."""
    import os
    import signal

    package = Package(story_dir)
    running = status(package)
    if running["running"]:
        raise refuse(
            Refusal(
                "page-running", f"the review page for this story is already running at {running['address']}",
                f"Ask the person to reload {running['address']}, or stop it with review serve --stop",
            )
        )  # fmt: skip
    server = make_server(
        story_dir, by, host=host, port=port, public_name=public_name, idle_minutes=idle_minutes, config=config
    )
    path = runtime_path(package)
    record = {
        "story": package.root.name,
        "address": server.address,
        "pid": os.getpid(),
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(json.dumps(record))
    os.chmod(path, 0o600)

    def end(signum: int, frame: Any) -> None:
        threading.Thread(target=server.shutdown, daemon=True).start()

    previous = {sig: signal.signal(sig, end) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        emit({"ok": True, "story": package.root.name, "address": server.address, "pid": os.getpid()})
        server.serve_forever(poll_interval=0.2)
    finally:
        server.server_close()
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        held = _read_runtime(path)
        if held is not None and held.get("pid") == os.getpid():
            path.unlink(missing_ok=True)
    reason = "idle" if server.stopped.is_set() else "stopped"
    return {
        "ok": True,
        "stopped": reason,
        "text": f"The review page {'stopped after being idle' if reason == 'idle' else 'stopped'}.",
    }
