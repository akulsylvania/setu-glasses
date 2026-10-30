"""Pre-push check: no API keys, .env files or proprietary artefacts in the repository."""

from __future__ import annotations

import re
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "__pycache__", "node_modules"}
PRIVATE_SUFFIXES = {".pt", ".pth", ".npz", ".a", ".ckpt", ".safetensors", ".wav", ".flac", ".mp4"}
KEY_PATTERNS = [
    re.compile(r"sk_car_[A-Za-z0-9]{10,}"),                       # Cartesia
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),                       # OpenAI-style
    re.compile(r"secret_[A-Za-z0-9_-]{16,}"),                     # Lambda-style
    re.compile(r"(?i)(api[_-]?key|token|subscription-key)\s*[=:]\s*['\"]?[A-Za-z0-9_\-]{24,}"),
    re.compile(r"\b[a-f0-9]{40}\b"),                              # Deepgram-style hex key
]
ALLOW = re.compile(r"change-me|YOUR|example|XXXX")


def scan(root: Path) -> list[str]:
    hits = []
    for p in root.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts) or not p.is_file():
            continue
        rel = p.relative_to(root)
        published_media = rel.parts[0] == "media" and p.suffix.lower() in (".mp4", ".png", ".jpg")
        if p.name == ".env" or (p.suffix.lower() in PRIVATE_SUFFIXES and not published_media):
            hits.append(f"{rel}: private file type (should be gitignored or removed)")
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if ALLOW.search(line):
                continue
            if any(rx.search(line) for rx in KEY_PATTERNS):
                hits.append(f"{rel}:{n}: looks like a secret")
    return hits
