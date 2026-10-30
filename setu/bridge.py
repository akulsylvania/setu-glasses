"""HTTP bridge Bolna calls during a conversation (custom functions + webhook).

    POST /bolna/ask_user          {"question": "...", "session": "..."} -> {"status", "say", ...}
    POST /bolna/get_user_answer   {"session": "..."}
    POST /bolna/webhook           Bolna execution updates
    GET  /health

Expose it publicly with e.g. `cloudflared tunnel --url http://localhost:8787` and set SETU_PUBLIC_URL.
Custom functions authenticate with `Authorization: Bearer <SETU_BRIDGE_TOKEN>`.
"""

from __future__ import annotations

import hmac
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .relay import Relay


def make_handler(relay: Relay, token: str | None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):   # keep the console for relay events
            pass

        def _send(self, code: int, obj: dict) -> None:
            body = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _authorised(self) -> bool:
            if not token:
                return True
            got = self.headers.get("Authorization", "")
            return hmac.compare_digest(got, f"Bearer {token}")

        def _params(self) -> dict:
            q = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(self.path).query))
            n = int(self.headers.get("Content-Length") or 0)
            if n:
                raw = self.rfile.read(n)
                try:
                    q |= json.loads(raw)
                except ValueError:
                    q |= dict(urllib.parse.parse_qsl(raw.decode("utf-8", "replace")))
            return q

        def do_GET(self):
            if urllib.parse.urlparse(self.path).path == "/health":
                return self._send(200, {"ok": True, "active_session": relay.active.id if relay.active else None})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            path = urllib.parse.urlparse(self.path).path
            p = self._params()
            if path == "/bolna/webhook":
                relay.on_webhook(p)
                return self._send(200, {"ok": True})
            if not self._authorised():
                return self._send(401, {"error": "unauthorised"})
            if path == "/bolna/ask_user":
                return self._send(200, relay.ask(str(p.get("question", "")), p.get("session")))
            if path == "/bolna/get_user_answer":
                return self._send(200, relay.get_answer(p.get("session")))
            self._send(404, {"error": "not found"})

    return Handler


def serve(relay: Relay, port: int = 8787, token: str | None = None, background: bool = True) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer(("0.0.0.0", port), make_handler(relay, token))
    if background:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    else:
        srv.serve_forever()
    return srv
