"""Sarvam AI: Bulbul TTS (11 Indian languages), Saaras STT, text translation.

Docs: https://docs.sarvam.ai  (auth header: api-subscription-key)
"""

from __future__ import annotations

import base64
import json

from .. import http
from ..config import bcp47

BASE = "https://api.sarvam.ai"


class Sarvam:
    def __init__(self, api_key: str, speaker: str = "shubh", tts_model: str = "bulbul:v3",
                 stt_model: str = "saaras:v4") -> None:
        self.key = api_key
        self.speaker = speaker
        self.tts_model = tts_model
        self.stt_model = stt_model

    @property
    def _h(self) -> dict:
        return {"api-subscription-key": self.key}

    def tts(self, text: str, lang: str = "en", sample_rate: int = 22050, pace: float = 1.0) -> bytes:
        """-> WAV bytes."""
        d = http.call_json("POST", f"{BASE}/text-to-speech", headers=self._h, body={
            "text": text, "language_code": bcp47(lang), "model": self.tts_model, "speaker": self.speaker,
            "pace": pace, "speech_sample_rate": sample_rate})
        return base64.b64decode("".join(d["audios"]))

    def stt(self, audio: bytes, lang: str = "unknown", filename: str = "audio.wav",
            timestamps: bool = True, keyterms: list[str] | None = None) -> dict:
        """-> {transcript, language_code, timestamps: {words, start_time_seconds, end_time_seconds}}"""
        fields = {"model": self.stt_model, "language_code": "unknown" if lang == "unknown" else bcp47(lang),
                  "with_timestamps": "true" if timestamps else "false"}
        if keyterms:
            fields["keyterms"] = json.dumps(keyterms[:50])
        body, ctype = http.multipart(fields, {"file": (filename, audio, "audio/wav")})
        _, content, _ = http.call("POST", f"{BASE}/speech-to-text", headers=self._h | {"Content-Type": ctype},
                                  raw=body, timeout=120)
        return json.loads(content)

    def translate(self, text: str, target: str, source: str = "en", model: str = "sarvam-translate:v1") -> str:
        d = http.call_json("POST", f"{BASE}/translate", headers=self._h, body={
            "input": text, "source_language_code": bcp47(source), "target_language_code": bcp47(target),
            "model": model})
        return d["translated_text"]
