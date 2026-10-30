"""LLM layer: context-aware choice among the recogniser's candidates, and phrase -> natural sentence.

The LLM never invents what the wearer said. It may only pick one of the recogniser's top-k
candidates (or none), using the conversation context, e.g. the caller just asked a yes/no question.
Works with any OpenAI-compatible chat endpoint: Sarvam (https://api.sarvam.ai/v2, sarvam-105b),
Simplismart, OpenAI, Groq. Without an LLM configured everything falls back to deterministic rules.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from . import http
from .decoder import Hypothesis
from .phrases import STAY_STILL, get, render

YES_NO_START = re.compile(r"^\s*(do|does|did|are|is|was|were|can|could|will|would|shall|should|have|has|may)\b", re.I)


class LLM:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 20) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def chat(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 200) -> str:
        d = http.call_json("POST", f"{self.base_url}/chat/completions", timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.api_key}"},
                           body={"model": self.model, "messages": messages,
                                 "temperature": temperature, "max_tokens": max_tokens})
        return d["choices"][0]["message"]["content"].strip()

    @classmethod
    def from_settings(cls, s) -> "LLM | None":
        if s.llm_base_url and s.llm_api_key and s.llm_model:
            return cls(s.llm_base_url, s.llm_api_key, s.llm_model)
        return None


@dataclass
class Choice:
    phrase: str | None        # None = nothing fits, ask the wearer to repeat
    prob: float
    reason: str


def context_prior(phrase: str, context: str | None) -> float:
    """Cheap rule prior used without an LLM: a yes/no question makes yes/no likelier."""
    if not context:
        return 1.0
    if YES_NO_START.match(context) or context.strip().endswith("?") and " or " not in context:
        return 2.0 if phrase in ("yes", "no") else 1.0
    return 1.0


def _parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def choose(hyps: list[Hypothesis], context: str | None = None, llm: LLM | None = None,
           min_prob: float = 0.0) -> Choice:
    cands = [h for h in hyps if h.phrase != STAY_STILL]
    if not cands or hyps[0].phrase == STAY_STILL and hyps[0].prob >= 0.5:
        return Choice(None, hyps[0].prob if hyps else 0.0, "wearer is not mouthing")
    scored = sorted(cands, key=lambda h: -h.prob * context_prior(h.phrase, context))
    rule = Choice(scored[0].phrase, scored[0].prob, "sensor top-1" if scored[0] is cands[0] else "sensor + context prior")
    if llm is not None and context:
        listing = "\n".join(f"{i}. \"{h.phrase}\" (sensor probability {h.prob:.2f})" for i, h in enumerate(cands[:5]))
        msg = [{"role": "system", "content":
                "You help a person who speaks silently through sensing glasses. A recogniser proposes candidate "
                "phrases. Pick the candidate the person most likely mouthed, given the sensor probabilities and "
                "what was just said to them. Never invent a phrase that is not listed. If none fits, choose -1. "
                "Answer only JSON: {\"choice\": <index or -1>, \"why\": \"<short>\"}"},
               {"role": "user", "content": f"They were just asked: \"{context}\"\nCandidates:\n{listing}"}]
        try:
            d = _parse_json(llm.chat(msg, temperature=0.0, max_tokens=80))
            i = int(d.get("choice", -2))
            if i == -1:
                return Choice(None, 0.0, f"llm: none fits ({d.get('why', '')})")
            if 0 <= i < len(cands[:5]):
                rule = Choice(cands[i].phrase, cands[i].prob, f"llm: {d.get('why', '')}")
        except Exception as e:                    # the LLM is an improvement, never a dependency
            rule.reason += f" (llm unavailable: {type(e).__name__})"
    if rule.phrase is not None and rule.prob < min_prob:
        return Choice(None, rule.prob, f"below confidence {min_prob:.2f}")
    return rule


TEMPLATES = {
    "call_opening": "Hello, this is Setu calling for {user}. {user} can't speak out loud right now and is answering "
                    "through silent speech glasses, so replies may take a few seconds. {user} wanted to call you.",
}


def expand(phrase: str, user: str, situation: str, lang: str = "en", llm: LLM | None = None) -> str:
    """One natural sentence said on the wearer's behalf, e.g. 'i am in pain' -> a caller-ready sentence."""
    p = get(phrase)
    base = render(p, lang) if p else phrase
    if llm is None:
        return base[:1].upper() + base[1:] + ("" if base.endswith((".", "?", "!")) else ".")
    msg = [{"role": "system", "content":
            f"Rewrite the wearer's silent phrase as ONE short sentence spoken on their behalf to the other "
            f"person. Language: {lang}. Keep the meaning exactly; add no facts. Wearer's name: {user}."},
           {"role": "user", "content": f"Situation: {situation}\nPhrase: \"{phrase}\""}]
    try:
        return llm.chat(msg, temperature=0.3, max_tokens=60).strip().strip('"')
    except Exception:
        return expand(phrase, user, situation, lang, None)
