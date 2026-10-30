"""Deepgram Nova-3 pre-recorded STT with word timestamps (English or multilingual code-switching).

Docs: https://developers.deepgram.com/reference/speech-to-text/listen-pre-recorded
"""

from __future__ import annotations

import urllib.parse

from .. import http

BASE = "https://api.deepgram.com/v1/listen"


class Deepgram:
    def __init__(self, api_key: str, model: str = "nova-3") -> None:
        self.key = api_key
        self.model = model

    def transcribe(self, audio: bytes, lang: str = "en", mime: str = "audio/wav") -> dict:
        """-> {transcript, words: [{w, start, end, conf}]}. lang="multi" for code-switched speech."""
        q = urllib.parse.urlencode({"model": self.model, "language": lang, "smart_format": "true",
                                    "punctuate": "true"})
        d = http.call_json("POST", f"{BASE}?{q}", raw=audio, timeout=120,
                           headers={"Authorization": f"Token {self.key}", "Content-Type": mime})
        alt = d["results"]["channels"][0]["alternatives"][0]
        return {"transcript": alt.get("transcript", ""),
                "words": [{"w": w["word"], "start": w["start"], "end": w["end"], "conf": w.get("confidence")}
                          for w in alt.get("words", [])]}
