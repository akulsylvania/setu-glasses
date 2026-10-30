"""Multilingual data acquisition with partner speech APIs.

Training data for the recogniser is paired sensor + audio + video: the wearer reads prompts aloud while
the glasses record, and the audio is transcribed with word timings to label the sensor stream. This
module is the public half of that pipeline (the sensor half is private):

  label        audio -> word-timed transcript with Deepgram Nova-3 and/or Sarvam Saaras v4.
               Run both and keep an utterance only when they agree (word edit ratio <= 25%), the
               same quality gate our in-house labeller uses. Works in English, Hindi and 9 more
               Indian languages, so new-language sessions need no manual transcription.
  prompts      TTS-paced prompts for *silent* sessions: there is no audio when the wearer only
               mouths, so each prompt is first played with Sarvam / Cartesia TTS, the wearer mouths
               along, and the TTS word timings become the (approximate) labels.
  translate    phrase packs / reading prompts into other languages with Sarvam Translate.

Output is plain JSON next to the input file: <name>.stt.json / prompts manifest.
"""

from __future__ import annotations

import io
import json
import wave
from pathlib import Path

from .voice import Deepgram, Sarvam


def wav_duration(wav: bytes) -> float:
    with wave.open(io.BytesIO(wav)) as w:
        return w.getnframes() / float(w.getframerate())


def edit_ratio(a: str, b: str) -> float:
    """Word-level edit distance / reference length (0 = identical)."""
    x, y = a.lower().split(), b.lower().split()
    d = list(range(len(y) + 1))
    for i, xa in enumerate(x, 1):
        prev, d[0] = d[0], i
        for j, yb in enumerate(y, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (xa != yb))
    return d[-1] / max(1, len(x))


def _clean(text: str) -> str:
    return "".join(c for c in text.lower() if c.isalnum() or c.isspace() or ord(c) > 127)


def label(audio_path: str | Path, lang: str = "en", deepgram: Deepgram | None = None,
          sarvam: Sarvam | None = None, max_disagreement: float = 0.25, write: bool = True) -> dict:
    audio = Path(audio_path).read_bytes()
    out: dict = {"file": Path(audio_path).name, "language": lang, "providers": {}}
    if deepgram:
        out["providers"]["deepgram"] = deepgram.transcribe(audio, "multi" if lang not in ("en",) else "en")
    if sarvam:
        r = sarvam.stt(audio, lang, Path(audio_path).name)
        ts = r.get("timestamps") or {}
        out["providers"]["sarvam"] = {
            "transcript": r.get("transcript", ""), "language_code": r.get("language_code"),
            "segments": [{"text": w, "start": s, "end": e} for w, s, e in
                         zip(ts.get("words", []), ts.get("start_time_seconds", []), ts.get("end_time_seconds", []))]}
    texts = [_clean(v["transcript"]) for v in out["providers"].values()]
    if len(texts) == 2:
        out["disagreement"] = round(edit_ratio(texts[0], texts[1]), 3)
        out["accepted"] = out["disagreement"] <= max_disagreement
    else:
        out["accepted"] = bool(texts and texts[0].strip())
    if write:
        Path(audio_path).with_suffix(".stt.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                            encoding="utf-8")
    return out


def tts_prompts(sentences: list[str], out_dir: str | Path, speaker, lang: str = "en") -> dict:
    """Synthesize paced prompts for silent sessions. `speaker` = setu.voice.Speaker."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    items = []
    for i, text in enumerate(sentences):
        prov, wav = speaker.synthesize(text, lang)
        if wav is None:
            raise RuntimeError("no TTS provider configured (set SARVAM_API_KEY or CARTESIA_API_KEY)")
        f = out / f"prompt_{i:04d}.wav"
        f.write_bytes(wav)
        items.append({"i": i, "text": text, "file": f.name, "provider": prov, "duration_s": round(wav_duration(wav), 3)})
    manifest = {"language": lang, "prompts": items}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return manifest


def translate_lines(lines: list[str], sarvam: Sarvam, target: str, source: str = "en") -> dict[str, str]:
    return {line: sarvam.translate(line, target, source) for line in lines}
