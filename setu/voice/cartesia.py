"""Cartesia Sonic TTS: low-latency English voice, including the wearer's own cloned voice.

Docs: https://docs.cartesia.ai/api-reference/tts/bytes
"""

from __future__ import annotations

from .. import http

BASE = "https://api.cartesia.ai"
VERSION = "2026-08-14"


class Cartesia:
    def __init__(self, api_key: str, voice_id: str, model: str = "sonic-3.5") -> None:
        self.key = api_key
        self.voice_id = voice_id
        self.model = model

    def tts(self, text: str, lang: str = "en", sample_rate: int = 24000) -> bytes:
        """-> WAV bytes (16-bit PCM)."""
        _, content, _ = http.call("POST", f"{BASE}/tts/bytes", headers={
            "Authorization": f"Bearer {self.key}", "Cartesia-Version": VERSION}, body={
            "model_id": self.model, "transcript": text, "voice": {"id": self.voice_id}, "language": lang,
            "output_format": {"container": "wav", "encoding": "pcm_s16le", "sample_rate": sample_rate}})
        return content
