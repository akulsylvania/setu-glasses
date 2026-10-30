"""Offline tests: every partner API call is intercepted, nothing touches the network.

    python -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import json
import threading
import time
import unittest
import urllib.request
from unittest import mock

from setu import http
from setu.agent import Bolna, build_agent_spec
from setu.bridge import serve
from setu.config import Settings
from setu.datasets import edit_ratio, label
from setu.decoder import Hypothesis, JsonlDecoder, Utterance, parse_line
from setu.llm import LLM, choose, expand
from setu.phrases import PHRASES, get, render
from setu.relay import Relay
from setu.voice import Cartesia, Deepgram, Sarvam, Speaker


class FakeHTTP:
    """Records requests and returns canned responses keyed by URL substring."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, headers=None, body=None, raw=None, timeout=60):
        self.calls.append({"method": method, "url": url, "headers": headers or {}, "body": body, "raw": raw})
        for key, resp in self.routes.items():
            if key in url:
                return 200, resp if isinstance(resp, bytes) else json.dumps(resp).encode(), {}
        raise AssertionError(f"unexpected request {method} {url}")


def H(*pairs):
    return [Hypothesis(p, q) for p, q in pairs]


def U(*pairs):
    return Utterance(0.0, [Hypothesis(p, q) for p, q in pairs])


class PhraseTests(unittest.TestCase):
    def test_phrase_set(self):
        self.assertEqual(len(PHRASES), 20)
        self.assertEqual(get("Call my family").action, "call")
        self.assertEqual(render(get("i need water"), "hi"), "मुझे पानी चाहिए")
        self.assertEqual(render(get("i need water"), "ta"), "i need water")   # until generated


class DecoderTests(unittest.TestCase):
    def test_parse_and_replay(self):
        u = parse_line('{"t": 1.5, "top": [["no", 0.2], ["yes", 0.7]]}')
        self.assertEqual(u.best.phrase, "yes")
        us = list(JsonlDecoder("samples/live_format.jsonl", follow=False).utterances())
        self.assertEqual([x.best.phrase for x in us], ["good morning", "(stay still)", "play music"])
        self.assertTrue(us[1].is_reject)


class ChooseTests(unittest.TestCase):
    def test_reject_and_threshold(self):
        self.assertIsNone(choose(H(("(stay still)", 0.8), ("yes", 0.1))).phrase)
        self.assertIsNone(choose(H(("yes", 0.2), ("no", 0.19)), min_prob=0.35).phrase)

    def test_yes_no_context_prior(self):
        u = U(("i need water", 0.40), ("yes", 0.30), ("no", 0.10))
        self.assertEqual(choose(u.hyps).phrase, "i need water")
        self.assertEqual(choose(u.hyps, "Are you okay?").phrase, "yes")

    def test_llm_can_only_pick_candidates(self):
        llm = LLM("https://llm.example/v1", "k", "m")
        fake = FakeHTTP({"chat/completions": {"choices": [{"message": {"content": '{"choice": 1, "why": "asked about thirst"}'}}]}})
        with mock.patch.object(http, "call", fake):
            c = choose(H(("i am hungry", 0.45), ("i need water", 0.40)), "Are you thirsty?", llm)
        self.assertEqual(c.phrase, "i need water")
        self.assertEqual(fake.calls[0]["headers"]["Authorization"], "Bearer k")
        bad = FakeHTTP({"chat/completions": {"choices": [{"message": {"content": '{"choice": 7}'}}]}})
        with mock.patch.object(http, "call", bad):
            self.assertEqual(choose(H(("no", 0.5), ("yes", 0.4)), "Is it raining?", llm).phrase, "no")

    def test_llm_failure_falls_back(self):
        llm = LLM("https://llm.example/v1", "k", "m")
        with mock.patch.object(http, "call", side_effect=OSError("offline")):
            c = choose(H(("yes", 0.6), ("no", 0.3)), "Are you okay?", llm)
            self.assertEqual(c.phrase, "yes")
            self.assertIn("llm unavailable", c.reason)
            self.assertEqual(expand("i am in pain", "Akul", "call", "en", llm), "I am in pain.")


class ProviderTests(unittest.TestCase):
    def test_sarvam_tts_stt_translate(self):
        wav = b"RIFF....WAVE"
        fake = FakeHTTP({"text-to-speech": {"audios": [base64.b64encode(wav).decode()]},
                         "speech-to-text": {"transcript": "नमस्ते", "language_code": "hi-IN"},
                         "translate": {"translated_text": "தண்ணீர் வேண்டும்"}})
        sv = Sarvam("sk")
        with mock.patch.object(http, "call", fake):
            self.assertEqual(sv.tts("नमस्ते", "hi"), wav)
            self.assertEqual(sv.stt(b"x", "hi")["transcript"], "नमस्ते")
            self.assertEqual(sv.translate("i need water", "ta"), "தண்ணீர் வேண்டும்")
        tts = fake.calls[0]
        self.assertEqual(tts["headers"]["api-subscription-key"], "sk")
        self.assertEqual(tts["body"]["language_code"], "hi-IN")
        self.assertEqual(tts["body"]["model"], "bulbul:v3")
        self.assertIn(b'name="model"\r\n\r\nsaaras:v4', fake.calls[1]["raw"])
        self.assertEqual(fake.calls[2]["body"]["target_language_code"], "ta-IN")

    def test_cartesia_and_deepgram(self):
        fake = FakeHTTP({"cartesia.ai": b"WAVBYTES",
                         "deepgram.com": {"results": {"channels": [{"alternatives": [{"transcript": "hi there",
                                          "words": [{"word": "hi", "start": 0.1, "end": 0.3, "confidence": 0.9}]}]}]}}})
        with mock.patch.object(http, "call", fake):
            self.assertEqual(Cartesia("ck", "voice-1").tts("hello"), b"WAVBYTES")
            r = Deepgram("dk").transcribe(b"x")
        c = fake.calls[0]
        self.assertEqual(c["headers"]["Cartesia-Version"], "2026-08-14")
        self.assertEqual(c["body"]["voice"], {"id": "voice-1"})
        self.assertEqual(r["words"][0], {"w": "hi", "start": 0.1, "end": 0.3, "conf": 0.9})
        self.assertIn("model=nova-3", fake.calls[1]["url"])
        self.assertEqual(fake.calls[1]["headers"]["Authorization"], "Token dk")

    def test_speaker_routing(self):
        s = Settings(sarvam_api_key="sk", cartesia_api_key="ck", cartesia_voice_id="v")
        sp = Speaker(s, play=False)
        self.assertEqual(sp.provider_for("en"), "cartesia")
        self.assertEqual(sp.provider_for("hi"), "sarvam")
        self.assertEqual(Speaker(Settings(), play=False).provider_for("hi"), "os")


class AgentTests(unittest.TestCase):
    def test_spec_per_language(self):
        en = build_agent_spec("https://b.example/", "tok", "en", cartesia_voice_id="v")
        t = en["agent_config"]["tasks"][0]["tools_config"]
        self.assertEqual(t["synthesizer"]["provider"], "cartesia")
        self.assertEqual(t["transcriber"]["provider"], "deepgram")
        self.assertEqual(t["input"]["provider"], "plivo")
        names = [x["name"] for x in t["api_tools"]["tools"]]
        self.assertEqual(names, ["ask_user", "get_user_answer"])
        ask = t["api_tools"]["tools"][0]
        self.assertEqual(ask["key"], "custom_task")
        self.assertEqual(ask["value"]["url"], "https://b.example/bolna/ask_user")
        self.assertEqual(ask["value"]["param"]["question"], "%(question)s")
        self.assertEqual(en["agent_config"]["webhook_url"], "https://b.example/bolna/webhook")
        hi = build_agent_spec("https://b.example", "tok", "hi", telephony="exotel")["agent_config"]["tasks"][0]["tools_config"]
        self.assertEqual((hi["synthesizer"]["provider"], hi["transcriber"]["provider"], hi["input"]["provider"]),
                         ("sarvam", "sarvam", "exotel"))
        self.assertEqual(hi["transcriber"]["model"], "saaras:v4")
        kalpa = build_agent_spec("https://b", "t", "hi", voice="kalpa")["agent_config"]["tasks"][0]["tools_config"]
        self.assertEqual(kalpa["synthesizer"]["provider"], "kalpa")
        custom = build_agent_spec("https://b", "t", "en", custom_llm_url="https://api.sarvam.ai/v2/", custom_llm_model="sarvam-105b")
        self.assertEqual(custom["agent_config"]["tasks"][0]["tools_config"]["llm_agent"]["llm_config"]["base_url"],
                         "https://api.sarvam.ai/v2")
        with self.assertRaises(ValueError):
            build_agent_spec("https://b", "t", "xx")

    def test_bolna_client(self):
        fake = FakeHTTP({"/v2/agent": {"agent_id": "ag1", "state": "created"}, "/call": {"execution_id": "ex1"},
                         "/executions/ex1": {"id": "ex1", "status": "completed", "transcript": "..."}})
        b = Bolna("bk")
        with mock.patch.object(http, "call", fake):
            self.assertEqual(b.create_agent({"agent_config": {}}), "ag1")
            self.assertEqual(b.make_call("ag1", "+911234567890", {"user_name": "A"}, "+918000000000"), "ex1")
            self.assertEqual(b.wait("ex1", poll_s=0)["status"], "completed")
        call = fake.calls[1]
        self.assertEqual(call["headers"]["Authorization"], "Bearer bk")
        self.assertEqual(call["body"]["recipient_phone_number"], "+911234567890")
        self.assertEqual(call["body"]["from_phone_number"], "+918000000000")


class RelayTests(unittest.TestCase):
    def make(self, bolna=None):
        s = Settings(user_name="Akul", bolna_agent_id="ag1", contacts={"family": "+911234567890"})
        return Relay(s, speaker=None, bolna=bolna, ask_timeout_s=2)

    def test_call_phrase_starts_bolna_call(self):
        bolna = mock.Mock()
        bolna.make_call.return_value = "ex9"
        r = self.make(bolna)
        r.on_utterance(U(("call my family", 0.7), ("call the nurse", 0.2)))
        agent_id, number, user_data, _ = bolna.make_call.call_args.args
        self.assertEqual((agent_id, number), ("ag1", "+911234567890"))
        self.assertEqual(user_data["session_id"], r.active.id)
        self.assertIn("Akul", user_data["opening_line"])

    def test_question_answer_loop(self):
        r = self.make()
        r.start_call("family", "test")
        out = {}
        t = threading.Thread(target=lambda: out.update(r.ask("Do you need anything?")))
        t.start()
        time.sleep(0.1)
        r.on_utterance(U(("(stay still)", 0.8), ("no", 0.1)))        # nothing mouthed yet: keep waiting
        r.on_utterance(U(("i need water", 0.5), ("i am hungry", 0.3)))
        t.join(3)
        self.assertEqual(out["status"], "answered")
        self.assertEqual(out["phrase"], "i need water")
        self.assertEqual(out["say"], "I need water.")

    def test_pending_then_get_answer(self):
        r = self.make()
        r.start_call("family", "test")
        self.assertEqual(r.ask("Are you okay?", timeout_s=0.05)["status"], "pending")
        r.on_utterance(U(("yes", 0.6), ("no", 0.3)))
        self.assertEqual(r.get_answer(timeout_s=0.05)["phrase"], "yes")

    def test_bridge_http(self):
        r = self.make()
        r.start_call("family", "test")
        srv = serve(r, port=0, token="tok")
        port = srv.server_address[1]

        def post(path, body, token="tok"):
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
                                         method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    return resp.status, json.loads(resp.read())
            except urllib.error.HTTPError as e:
                return e.code, {}

        self.assertEqual(post("/bolna/ask_user", {"question": "x"}, token="wrong")[0], 401)
        threading.Timer(0.2, lambda: r.on_utterance(U(("no", 0.7), ("yes", 0.2)))).start()
        code, body = post("/bolna/ask_user", {"question": "Are you cold?", "session": r.active.id})
        self.assertEqual((code, body["phrase"]), (200, "no"))
        self.assertEqual(post("/bolna/webhook", {"id": None, "status": "completed"})[0], 200)
        self.assertIsNone(r.active)
        srv.shutdown()


class DatasetTests(unittest.TestCase):
    def test_edit_ratio(self):
        self.assertEqual(edit_ratio("i need water", "i need water"), 0.0)
        self.assertAlmostEqual(edit_ratio("i need water now", "i need water"), 0.25)

    def test_label_agreement_gate(self):
        import tempfile, os
        fake = FakeHTTP({"deepgram.com": {"results": {"channels": [{"alternatives": [{"transcript": "I need water.", "words": []}]}]}},
                         "speech-to-text": {"transcript": "i need water", "language_code": "en-IN",
                                            "timestamps": {"words": ["i need water"], "start_time_seconds": [0.2],
                                                           "end_time_seconds": [1.1]}}})
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "s.wav")
            open(f, "wb").write(b"RIFF")
            with mock.patch.object(http, "call", fake):
                r = label(f, "en", Deepgram("dk"), Sarvam("sk"))
            self.assertTrue(r["accepted"])
            self.assertEqual(r["disagreement"], 0.0)
            self.assertEqual(r["providers"]["sarvam"]["segments"][0]["end"], 1.1)
            self.assertTrue(os.path.exists(os.path.join(d, "s.stt.json")))


class LiveToolingTests(unittest.TestCase):
    def test_doctor_reports_without_secrets(self):
        from setu.doctor import run
        s = Settings(sarvam_api_key="sk-sarvam-secret", deepgram_api_key="dg-secret")
        fake = FakeHTTP({"translate": {"translated_text": "मुझे पानी चाहिए"},
                         "text-to-speech": {"audios": [base64.b64encode(b"RIFF").decode()]},
                         "deepgram.com/v1/projects": {"projects": [{"project_id": "p"}]}})
        with mock.patch.object(http, "call", fake):
            rep = run(s)
        r = rep["results"]
        self.assertEqual((r["sarvam_translate"]["status"], r["sarvam_tts"]["status"], r["deepgram"]["status"]),
                         ("ok", "ok", "ok"))
        self.assertEqual(r["bolna"]["status"], "not configured")
        self.assertNotIn("secret", json.dumps(rep))
        with mock.patch.object(http, "call", side_effect=http.APIError(401, "bad key", "u")):
            self.assertEqual(run(s)["results"]["deepgram"]["detail"], "HTTP 401")

    def test_secret_scan(self):
        import os
        import tempfile
        from pathlib import Path
        from setu.secrets_scan import scan
        with tempfile.TemporaryDirectory() as d:
            Path(d, "ok.py").write_text('KEY = os.environ["SARVAM_API_KEY"]\n', encoding="utf-8")
            self.assertEqual(scan(Path(d)), [])
            fake_key = "sk_car_" + "q7" * 15          # built at runtime so this file itself scans clean
            Path(d, "bad.py").write_text(f'api_key = "{fake_key}"\n', encoding="utf-8")
            Path(d, ".env").write_text("BOLNA_API_KEY=x\n", encoding="utf-8")
            Path(d, "model.pt").write_bytes(b"x")
            self.assertEqual(len(scan(Path(d))), 3)
            os.remove(os.path.join(d, "bad.py"))


if __name__ == "__main__":
    unittest.main()
