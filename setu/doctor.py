"""`setu doctor`: check every configured partner key with one cheap real request.

Writes docs/live_status.json (provider -> ok / error / not configured, timestamp; never any secret),
a record of which partner services this install can reach.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from . import http
from .config import Settings


def _check(fn) -> dict:
    t0 = time.time()
    try:
        detail = fn()
        return {"status": "ok", "detail": detail, "ms": int((time.time() - t0) * 1000)}
    except http.APIError as e:
        return {"status": "error", "detail": f"HTTP {e.status}", "ms": int((time.time() - t0) * 1000)}
    except Exception as e:  # network, parsing
        return {"status": "error", "detail": type(e).__name__, "ms": int((time.time() - t0) * 1000)}


def run(s: Settings) -> dict:
    from .agent import Bolna
    from .llm import LLM
    from .voice import Cartesia, Deepgram, Sarvam

    out: dict[str, dict] = {}
    if s.bolna_api_key and s.bolna_agent_id:
        out["bolna"] = _check(lambda: "agent " + Bolna(s.bolna_api_key).get_agent(s.bolna_agent_id).get("agent_name", "found"))
    elif s.bolna_api_key:
        out["bolna"] = {"status": "key set", "detail": "run `setu create-agent` to verify"}
    if s.sarvam_api_key:
        sv = Sarvam(s.sarvam_api_key, s.sarvam_speaker)
        out["sarvam_translate"] = _check(lambda: sv.translate("I need water", "hi"))
        out["sarvam_tts"] = _check(lambda: f"{len(sv.tts('नमस्ते', 'hi'))} bytes")
    if s.cartesia_api_key and s.cartesia_voice_id:
        out["cartesia_tts"] = _check(lambda: f"{len(Cartesia(s.cartesia_api_key, s.cartesia_voice_id).tts('Hello.'))} bytes")
    if s.deepgram_api_key:
        out["deepgram"] = _check(lambda: f"{len(http.call_json('GET', 'https://api.deepgram.com/v1/projects', headers={'Authorization': f'Token {s.deepgram_api_key}'}).get('projects', []))} project(s)")
    llm = LLM.from_settings(s)
    if llm:
        out["llm"] = _check(lambda: llm.chat([{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=5))
    for name, need in (("bolna", "BOLNA_API_KEY"), ("sarvam_tts", "SARVAM_API_KEY"),
                       ("cartesia_tts", "CARTESIA_API_KEY + CARTESIA_VOICE_ID"), ("deepgram", "DEEPGRAM_API_KEY"),
                       ("llm", "LLM_BASE_URL + LLM_API_KEY + LLM_MODEL")):
        out.setdefault(name, {"status": "not configured", "detail": f"set {need}"})
    out["bridge"] = {"status": "ok" if s.public_url and s.bridge_token else "not configured",
                     "detail": "public URL + token set" if s.public_url and s.bridge_token else "set SETU_PUBLIC_URL + SETU_BRIDGE_TOKEN"}
    return {"checked_at": time.strftime("%Y-%m-%d %H:%M:%S %z"), "results": out}


def main(s: Settings, out_path: str | None = "docs/live_status.json") -> dict:
    rep = run(s)
    for k, v in rep["results"].items():
        print(f"  {k:18s} {v['status']:15s} {v.get('detail', '')}" + (f"  ({v['ms']} ms)" if "ms" in v else ""))
    if out_path:
        Path(out_path).write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"wrote {out_path}")
    return rep
