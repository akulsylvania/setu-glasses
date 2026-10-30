"""The Setu runtime: silent utterances in, actions out.

Outside a call:  phrase -> speak it aloud / start a Bolna call / send a device command.
Inside a call:   the Bolna agent asks a question (ask_user) -> spoken into the wearer's earpiece ->
                 the next silent utterance answers it -> LLM picks among the recogniser's candidates
                 using the question as context -> the agent says the answer.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field

from .config import LANGUAGES, Settings
from .decoder import Utterance
from .llm import LLM, TEMPLATES, Choice, choose, expand
from .phrases import get


@dataclass
class Question:
    text: str
    asked_at: float
    answer: dict | None = None
    done: threading.Event = field(default_factory=threading.Event)


@dataclass
class Session:
    id: str
    contact: str
    execution_id: str | None = None
    status: str = "starting"
    pending: Question | None = None
    last: Question | None = None      # most recent question, kept for get_user_answer after ask timed out
    log: list[dict] = field(default_factory=list)


class Relay:
    def __init__(self, settings: Settings, speaker=None, bolna=None, llm: LLM | None = None,
                 min_confidence: float = 0.35, ask_timeout_s: float = 12.0) -> None:
        self.s = settings
        self.speaker = speaker
        self.bolna = bolna
        self.llm = llm
        self.min_confidence = min_confidence
        self.ask_timeout_s = ask_timeout_s
        self.sessions: dict[str, Session] = {}
        self.active: Session | None = None
        self.events: list[dict] = []
        self.lock = threading.Lock()

    def _event(self, kind: str, **kw) -> dict:
        e = {"t": round(time.time(), 3), "kind": kind} | kw
        self.events.append(e)
        if self.active:
            self.active.log.append(e)
        print(f"[{kind}] " + ", ".join(f"{k}={v}" for k, v in kw.items()), flush=True)
        return e

    def _say_local(self, text: str) -> None:
        if self.speaker:
            self.speaker.say(text, self.s.language)

    # ------------------------------------------------------------ utterances from the glasses
    def on_utterance(self, u: Utterance) -> Choice:
        q = self.active.pending if self.active else None
        c = choose(u.hyps, q.text if q else None, self.llm, self.min_confidence)
        self._event("utterance", top=[(h.phrase, round(h.prob, 2)) for h in u.hyps[:3]], chosen=c.phrase,
                    reason=c.reason)
        if q is not None:
            self._answer(q, c)
        elif c.phrase is not None:
            self.act(c.phrase)
        return c

    def act(self, phrase: str) -> str:
        p = get(phrase)
        if p is None or p.action == "speak":
            text = expand(phrase, self.s.user_name, "speaking to someone nearby", self.s.language, None)
            self._say_local(text)
            return "speak"
        if p.action == "call":
            self.start_call(p.target, reason=f"{self.s.user_name} silently asked to call their {p.target}")
            return "call"
        self._event("device", command=p.target)
        return "device"

    # ------------------------------------------------------------ calls through Bolna
    def start_call(self, contact: str, reason: str) -> Session:
        number = self.s.contacts.get(contact)
        sess = Session(uuid.uuid4().hex[:8], contact)
        with self.lock:
            self.sessions[sess.id] = sess
            self.active = sess
        opening = TEMPLATES["call_opening"].format(user=self.s.user_name)
        user_data = {"user_name": self.s.user_name, "session_id": sess.id, "opening_line": opening,
                     "call_reason": reason, "language_name": LANGUAGES.get(self.s.language, "English")}
        if self.bolna is None or not number or not self.s.bolna_agent_id:
            sess.status = "dry-run"
            self._event("call", contact=contact, status="dry-run (Bolna not configured)")
            return sess
        sess.execution_id = self.bolna.make_call(self.s.bolna_agent_id, number, user_data, self.s.bolna_from_number)
        sess.status = "dialing"
        self._event("call", contact=contact, execution_id=sess.execution_id)
        self._say_local(f"Calling your {contact}.")
        return sess

    def _session(self, session_id: str | None) -> Session | None:
        return self.sessions.get(session_id or "") or self.active

    def ask(self, question: str, session_id: str | None = None, timeout_s: float | None = None) -> dict:
        """ask_user custom function: speak the question to the wearer, wait for the silent answer."""
        sess = self._session(session_id)
        if sess is None:
            return {"status": "none", "say": "There is no active Setu session."}
        q = Question(question, time.time())
        sess.pending = sess.last = q
        self._event("question", text=question)
        self._say_local(question)
        q.done.wait(self.ask_timeout_s if timeout_s is None else timeout_s)
        return q.answer or {"status": "pending", "say": f"{self.s.user_name} is still answering."}

    def get_answer(self, session_id: str | None = None, timeout_s: float | None = None) -> dict:
        sess = self._session(session_id)
        q = (sess.pending or sess.last) if sess else None
        if q is None:
            return {"status": "none", "say": "There is no open question."}
        q.done.wait(self.ask_timeout_s if timeout_s is None else timeout_s)
        return q.answer or {"status": "pending", "say": f"{self.s.user_name} is still answering."}

    def _answer(self, q: Question, c: Choice) -> None:
        if c.phrase is None:
            q.answer = {"status": "none", "say": "", "reason": c.reason}
            self._say_local("Please mouth that again.")
            return   # keep the question open for another try
        sentence = expand(c.phrase, self.s.user_name, f"answering the question: {q.text}", self.s.language, self.llm)
        q.answer = {"status": "answered", "phrase": c.phrase, "confidence": round(c.prob, 2), "say": sentence,
                    "latency_s": round(time.time() - q.asked_at, 1)}
        self._event("answer", phrase=c.phrase, say=sentence)
        if self.active:
            self.active.pending = None
        q.done.set()

    def on_webhook(self, payload: dict) -> None:
        sess = next((s for s in self.sessions.values() if s.execution_id and s.execution_id == payload.get("id")),
                    self.active)
        status = payload.get("status")
        if sess and status:
            sess.status = status
        self._event("webhook", status=status, execution_id=payload.get("id"))
        if status in ("completed", "no-answer", "busy", "failed") and sess is self.active:
            self._say_local({"completed": "Call ended."}.get(status, f"Call {status}."))
            self.active = None
