"""Speech output for the wearer's local speaker / earpiece.

Routing: English -> Cartesia (the wearer's own cloned voice) when configured; Indian languages and
English fallback -> Sarvam Bulbul; nothing configured -> the OS voice (Windows) or console only.
In a phone call the same voices are used by the Bolna agent itself (see setu/agent/spec.py).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

from ..config import Settings
from .cartesia import Cartesia
from .deepgram import Deepgram
from .sarvam import Sarvam

__all__ = ["Speaker", "Sarvam", "Cartesia", "Deepgram"]


class Speaker:
    def __init__(self, settings: Settings, play: bool = True) -> None:
        self.s = settings
        self.play_audio = play
        self.sarvam = Sarvam(settings.sarvam_api_key, settings.sarvam_speaker) if settings.sarvam_api_key else None
        self.cartesia = (Cartesia(settings.cartesia_api_key, settings.cartesia_voice_id)
                         if settings.cartesia_api_key and settings.cartesia_voice_id else None)

    def provider_for(self, lang: str) -> str:
        if lang == "en" and self.cartesia:
            return "cartesia"
        if self.sarvam:
            return "sarvam"
        return "os"

    def synthesize(self, text: str, lang: str) -> tuple[str, bytes | None]:
        prov = self.provider_for(lang)
        if prov == "cartesia":
            return prov, self.cartesia.tts(text, lang)
        if prov == "sarvam":
            return prov, self.sarvam.tts(text, lang)
        return prov, None

    def say(self, text: str, lang: str | None = None) -> str:
        lang = lang or self.s.language
        prov, wav = self.synthesize(text, lang)
        print(f"[speak:{prov}:{lang}] {text}", flush=True)
        if self.play_audio:
            play_wav(wav) if wav else os_say(text)
        return prov


def play_wav(wav: bytes) -> None:
    if sys.platform == "win32":
        import winsound
        winsound.PlaySound(wav, winsound.SND_MEMORY)
        return
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(wav)
    for player in (["afplay", f.name], ["aplay", "-q", f.name]):
        try:
            subprocess.run(player, check=True)
            return
        except (OSError, subprocess.CalledProcessError):
            continue


def os_say(text: str) -> None:
    if sys.platform != "win32":
        return
    safe = "".join(c for c in text if c.isalnum() or c in " ,.!?'")
    cmd = ("Add-Type -AssemblyName System.Speech; "
           f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe.replace(chr(39), '')}')")
    subprocess.run(["powershell", "-NoProfile", "-Command", cmd],
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
