"""Drive the browser review page without a browser (004 task T003).

``start_page`` runs ``reviewpage``'s server in a thread on a free port; ``call`` talks to it with
``urllib.request`` and returns ``(status, headers, text)`` whatever the status. ``same_origin`` builds
the headers a page script sends on a state-changing request.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit


@dataclass
class Page:
    address: str  # the address the agent gives, token included
    token: str
    server: Any
    stop: Callable[[], None]

    @property
    def origin(self) -> str:
        parts = urlsplit(self.address)
        return f"{parts.scheme}://{parts.netloc}"

    def call(self, method: str, path: str, body: Any = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], str]:
        return call(method, self.origin + path, body, headers)

    def post(self, path: str, body: Any, **extra: str) -> tuple[int, Any]:
        """A POST as the page's script sends it; returns the status and the parsed JSON."""
        status, _, text = self.call("POST", path, body, {**same_origin(self.origin, self.token), **extra})
        try:
            return status, json.loads(text)
        except ValueError:
            return status, text

    def get(self, path: str = "/", token: bool = True) -> tuple[int, dict[str, str], str]:
        if path.startswith("/state"):
            return self.call("GET", path, headers={"X-EIL-Token": self.token} if token else {})
        joiner = "&" if "?" in path else "?"
        return self.call("GET", f"{path}{joiner}t={self.token}" if token else path)

    def state(self) -> Any:
        status, _, text = self.get("/state")
        assert status == 200, text
        return json.loads(text)


def start_page(story_dir: Path, by: str = "Ada Dev", **opts: Any) -> Page:
    """Start the page for ``story_dir`` in a thread (an OS-chosen free port unless ``port`` is given)."""
    from eil import reviewpage

    opts.setdefault("port", 0)
    server = reviewpage.make_server(story_dir, by, **opts)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()

    def stop() -> None:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    return Page(server.address, server.token, server, stop)


def call(
    method: str, url: str, body: Any = None, headers: dict[str, str] | None = None
) -> tuple[int, dict[str, str], str]:
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read().decode("utf-8")


def same_origin(origin: str, token: str) -> dict[str, str]:
    """The headers of a state-changing request from the page itself."""
    return {"Origin": origin, "Content-Type": "application/json", "X-EIL-Token": token}


def eil(root: Path, *argv: str) -> tuple[int, Any]:
    """Run the helper in-process on the story at ``root`` with ``--json``; ``(exit code, payload)``."""
    import io

    from eil import cli

    out, err = io.StringIO(), io.StringIO()
    code = cli.main([*argv, "--json", "--feature-dir", str(root)], cwd=root, stdout=out, stderr=err)
    text = out.getvalue()
    return code, (json.loads(text) if text.strip() else err.getvalue())
