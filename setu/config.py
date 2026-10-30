"""Settings from environment variables (and an optional .env file). See .env.example."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Languages the voice side supports end to end (Sarvam Bulbul TTS + Saaras STT through Bolna)
LANGUAGES = {
    "en": "English", "hi": "Hindi", "bn": "Bengali", "ta": "Tamil", "te": "Telugu", "gu": "Gujarati",
    "kn": "Kannada", "ml": "Malayalam", "mr": "Marathi", "pa": "Punjabi", "od": "Odia",
}


def bcp47(lang: str) -> str:
    """'hi' -> 'hi-IN' (Sarvam REST APIs want BCP-47; Bolna wants the short code)."""
    return lang if "-" in lang else f"{lang}-IN"


def load_dotenv(path: str | Path = ".env") -> None:
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name, "").strip()
    return v or default


@dataclass
class Settings:
    user_name: str = "the user"
    language: str = "en"
    # Bolna voice agent
    bolna_api_key: str | None = None
    bolna_agent_id: str | None = None
    bolna_from_number: str | None = None
    telephony: str = "plivo"                 # plivo | exotel (configured in the Bolna dashboard)
    public_url: str | None = None            # public https URL of `setu bridge` (cloudflared / ngrok)
    bridge_token: str | None = None
    contacts: dict[str, str] = field(default_factory=dict)   # "family" -> "+91..."
    # speech providers
    sarvam_api_key: str | None = None
    sarvam_speaker: str = "shubh"
    cartesia_api_key: str | None = None
    cartesia_voice_id: str | None = None     # the user's own (cloned) voice
    deepgram_api_key: str | None = None
    # LLM (any OpenAI-compatible endpoint: Sarvam, Simplismart, OpenAI, Groq ...)
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str | None = None

    @classmethod
    def from_env(cls, dotenv: str | Path = ".env") -> "Settings":
        load_dotenv(dotenv)
        contacts = json.loads(_env("SETU_CONTACTS", "{}"))
        return cls(
            user_name=_env("SETU_USER_NAME", "the user"), language=_env("SETU_LANGUAGE", "en"),
            bolna_api_key=_env("BOLNA_API_KEY"), bolna_agent_id=_env("BOLNA_AGENT_ID"),
            bolna_from_number=_env("BOLNA_FROM_NUMBER"), telephony=_env("SETU_TELEPHONY", "plivo"),
            public_url=_env("SETU_PUBLIC_URL"), bridge_token=_env("SETU_BRIDGE_TOKEN"), contacts=contacts,
            sarvam_api_key=_env("SARVAM_API_KEY"), sarvam_speaker=_env("SARVAM_SPEAKER", "shubh"),
            cartesia_api_key=_env("CARTESIA_API_KEY"), cartesia_voice_id=_env("CARTESIA_VOICE_ID"),
            deepgram_api_key=_env("DEEPGRAM_API_KEY"),
            llm_base_url=_env("LLM_BASE_URL"), llm_api_key=_env("LLM_API_KEY"), llm_model=_env("LLM_MODEL"),
        )
