"""Bolna REST client: create the relay agent, place calls, read executions.

Docs: https://www.bolna.ai/docs  (Authorization: Bearer <BOLNA_API_KEY>)
"""

from __future__ import annotations

import time

from .. import http

BASE = "https://api.bolna.ai"
FINAL = {"completed", "no-answer", "busy", "failed", "error", "canceled"}


class Bolna:
    def __init__(self, api_key: str, base: str = BASE) -> None:
        self.key = api_key
        self.base = base

    @property
    def _h(self) -> dict:
        return {"Authorization": f"Bearer {self.key}"}

    def create_agent(self, spec: dict) -> str:
        d = http.call_json("POST", f"{self.base}/v2/agent", headers=self._h, body=spec)
        return d["agent_id"]

    def get_agent(self, agent_id: str) -> dict:
        return http.call_json("GET", f"{self.base}/v2/agent/{agent_id}", headers=self._h)

    def make_call(self, agent_id: str, to: str, user_data: dict | None = None,
                  from_number: str | None = None, retries: int = 0) -> str:
        """Outbound call; `user_data` fills {{variables}} in the agent prompt and welcome message."""
        body = {"agent_id": agent_id, "recipient_phone_number": to, "user_data": user_data or {}}
        if from_number:
            body["from_phone_number"] = from_number
        if retries:
            body["retry_config"] = {"enabled": True, "max_retries": retries}
        d = http.call_json("POST", f"{self.base}/call", headers=self._h, body=body)
        return d.get("execution_id") or d.get("id")

    def get_execution(self, execution_id: str) -> dict:
        return http.call_json("GET", f"{self.base}/executions/{execution_id}", headers=self._h)

    def wait(self, execution_id: str, poll_s: float = 3.0, timeout_s: float = 900) -> dict:
        t0 = time.time()
        while True:
            d = self.get_execution(execution_id)
            if d.get("status") in FINAL or time.time() - t0 > timeout_s:
                return d
            time.sleep(poll_s)
