"""Minimal HTTP helpers (stdlib only, so the glasses runtime needs no extra packages).

Every provider client goes through `call`, which keeps tests simple: patch `setu.http.call`.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid


class APIError(RuntimeError):
    def __init__(self, status: int, body: str, url: str) -> None:
        super().__init__(f"HTTP {status} from {url}: {body[:300]}")
        self.status = status
        self.body = body
        self.url = url


def call(method: str, url: str, headers: dict | None = None, body: dict | None = None,
         raw: bytes | None = None, timeout: float = 60) -> tuple[int, bytes, dict]:
    """-> (status, content, headers). JSON `body` or `raw` bytes; raises APIError on 4xx/5xx."""
    hdrs = dict(headers or {})
    data = raw
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        raise APIError(e.code, e.read().decode("utf-8", "replace"), url) from None


def call_json(method: str, url: str, **kw) -> dict:
    _, content, _ = call(method, url, **kw)
    return json.loads(content) if content else {}


def multipart(fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> tuple[bytes, str]:
    """-> (body, content_type) for a multipart/form-data upload. files: name -> (filename, bytes, mime)."""
    boundary = uuid.uuid4().hex
    out = bytearray()
    for k, v in fields.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode("utf-8")
    for k, (fname, blob, mime) in files.items():
        out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fname}\"\r\n"
                f"Content-Type: {mime}\r\n\r\n").encode("utf-8")
        out += blob + b"\r\n"
    out += f"--{boundary}--\r\n".encode("utf-8")
    return bytes(out), f"multipart/form-data; boundary={boundary}"
