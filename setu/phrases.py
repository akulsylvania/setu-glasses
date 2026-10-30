"""The silent phrase set the recogniser is trained on, with what each phrase does.

v1 is a closed set of 20 phrases + a reject class ("stay still"), so the glasses never speak when
the wearer is not mouthing anything. Each phrase has an action:
    speak   say it aloud (local speaker or into the current call)
    call    place a phone call through the Bolna voice agent to a saved contact
    device  a control command for a paired phone / smart device
English and Hindi renderings ship with the repo; other languages are generated with Sarvam
Translate (`setu translate-phrases --lang ta`) into setu/data/phrases_<lang>.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA = Path(__file__).parent / "data"
STAY_STILL = "(stay still)"


@dataclass(frozen=True)
class Phrase:
    en: str
    hi: str
    action: str = "speak"        # speak | call | device
    target: str | None = None    # contact key for "call", command for "device"
    pack: str = "everyday"       # everyday | care | control


PHRASES: list[Phrase] = [
    Phrase("yes", "हाँ"),
    Phrase("no", "नहीं"),
    Phrase("thank you", "धन्यवाद"),
    Phrase("please wait", "कृपया रुकिए"),
    Phrase("say that again", "फिर से बोलिए"),
    Phrase("how are you", "आप कैसे हैं"),
    Phrase("good morning", "सुप्रभात"),
    Phrase("good night", "शुभ रात्रि"),
    Phrase("i love you", "मुझे तुमसे प्यार है"),
    Phrase("call my family", "मेरे परिवार को फ़ोन करो", "call", "family"),
    Phrase("play music", "गाना चलाओ", "device", "media.play", "control"),
    Phrase("stop", "रुको", "device", "media.stop", "control"),
    Phrase("turn on the light", "लाइट जला दो", "device", "light.on", "control"),
    Phrase("help me", "मेरी मदद करो", pack="care"),
    Phrase("i need water", "मुझे पानी चाहिए", pack="care"),
    Phrase("i am in pain", "मुझे दर्द हो रहा है", pack="care"),
    Phrase("i am hungry", "मुझे भूख लगी है", pack="care"),
    Phrase("i am cold", "मुझे ठंड लग रही है", pack="care"),
    Phrase("i need the bathroom", "मुझे बाथरूम जाना है", pack="care"),
    Phrase("call the nurse", "नर्स को बुलाओ", "call", "nurse", "care"),
]
BY_TEXT = {p.en: p for p in PHRASES}


def get(text: str) -> Phrase | None:
    return BY_TEXT.get(text.strip().lower())


def render(p: Phrase, lang: str = "en") -> str:
    """The phrase in `lang` (en / hi built in, others from setu/data/phrases_<lang>.json if generated)."""
    if lang == "en":
        return p.en
    if lang == "hi":
        return p.hi
    f = DATA / f"phrases_{lang}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8")).get(p.en, p.en)
    return p.en
