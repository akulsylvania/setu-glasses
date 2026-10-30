"""`setu` command line.

    setu phrases [--lang hi]                     list the phrase set
    setu agent-spec --out agents/x.json          render the Bolna relay agent (no network)
    setu create-agent [--lang hi --voice sarvam] create it in Bolna, prints BOLNA_AGENT_ID
    setu say "text" [--lang hi]                  speak through the configured TTS
    setu run --decoder live.jsonl [--port 8787]  live: glasses utterances -> speak / call / device + bridge
    setu simulate samples/demo_call.json         offline end-to-end call simulation (no keys needed)
    setu replay recogniser.jsonl                 recorded recogniser outputs -> actions (+ accuracy)
    setu doctor                                  check every partner key with one real request
    setu call family [--decoder live.jsonl]      live silent call through Bolna (type answers without glasses)
    setu check-secrets                           scan the repo for keys / private files before pushing
    setu label session.wav [--lang hi]           Deepgram + Sarvam word-timed labels with agreement gate
    setu prompts sentences.txt --out dir         TTS-paced prompts for silent recording sessions
    setu translate-phrases --lang ta             phrase pack -> setu/data/phrases_ta.json (Sarvam Translate)
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

from .config import LANGUAGES, Settings


def _settings(args) -> Settings:
    s = Settings.from_env(args.env)
    if getattr(args, "lang", None):
        s.language = args.lang
    return s


def cmd_phrases(args) -> None:
    from .phrases import PHRASES, render

    for p in PHRASES:
        print(f"{p.pack:9s} {p.action:6s} {p.en:22s} {render(p, args.lang or 'en')}")


def cmd_agent_spec(args) -> None:
    from .agent.spec import build_agent_spec

    s = _settings(args)
    spec = build_agent_spec(s.public_url or "https://YOUR-BRIDGE.example.com", s.bridge_token or "SETU_BRIDGE_TOKEN",
                            lang=s.language, voice=args.voice, telephony=args.telephony or s.telephony,
                            cartesia_voice_id=s.cartesia_voice_id or ("CARTESIA_VOICE_ID" if args.voice == "cartesia" else None),
                            custom_llm_url=args.custom_llm_url, custom_llm_model=args.custom_llm_model)
    text = json.dumps(spec, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"wrote {args.out}")
    else:
        print(text)


def cmd_create_agent(args) -> None:
    from .agent import Bolna, build_agent_spec

    s = _settings(args)
    if not (s.bolna_api_key and s.public_url and s.bridge_token):
        sys.exit("set BOLNA_API_KEY, SETU_PUBLIC_URL and SETU_BRIDGE_TOKEN first")
    spec = build_agent_spec(s.public_url, s.bridge_token, s.language, args.voice, args.telephony or s.telephony,
                            s.cartesia_voice_id, args.custom_llm_url, args.custom_llm_model)
    agent_id = Bolna(s.bolna_api_key).create_agent(spec)
    print(f"BOLNA_AGENT_ID={agent_id}")


def cmd_say(args) -> None:
    from .voice import Speaker

    s = _settings(args)
    Speaker(s).say(args.text, s.language)


def _build_relay(s: Settings, play: bool = True):
    from .agent import Bolna
    from .llm import LLM
    from .relay import Relay
    from .voice import Speaker

    return Relay(s, Speaker(s, play), Bolna(s.bolna_api_key) if s.bolna_api_key else None, LLM.from_settings(s))


def cmd_run(args) -> None:
    from .bridge import serve
    from .decoder import JsonlDecoder

    s = _settings(args)
    relay = _build_relay(s, not args.mute)
    if args.min_confidence is not None:
        relay.min_confidence = args.min_confidence
    serve(relay, args.port, s.bridge_token)
    print(f"bridge on :{args.port}  (public: {s.public_url or 'not set'})  reading {args.decoder}", flush=True)
    for u in JsonlDecoder(args.decoder, follow=not args.replay).utterances():
        relay.on_utterance(u)


def cmd_simulate(args) -> None:
    """Replays a scripted call: questions from the other side + the wearer's recorded top-k answers."""
    from .decoder import Hypothesis, Utterance
    from .llm import LLM
    from .relay import Relay
    from .voice import Speaker

    s = _settings(args)
    script = json.loads(Path(args.script).read_text(encoding="utf-8"))
    relay = Relay(s, Speaker(s, play=not args.mute), bolna=None, llm=LLM.from_settings(s), ask_timeout_s=5)
    print(f"== simulation: {script.get('title', args.script)}\n")
    for step in script["steps"]:
        if "utterance" in step:
            u = Utterance(time.time(), [Hypothesis(p, q) for p, q in step["utterance"]])
            relay.on_utterance(u)
        elif "caller" in step:
            print(f"\n[caller] {step['caller']}")
            res: dict = {}
            t = threading.Thread(target=lambda: res.update(relay.ask(step["caller"])))
            t.start()
            time.sleep(0.2)
            for top in step.get("answers", []):
                relay.on_utterance(Utterance(time.time(), [Hypothesis(p, q) for p, q in top]))
            t.join()
            print(f"[agent says] {res.get('say')}")
    print("\n== events:", len(relay.events))


def cmd_doctor(args) -> None:
    from .doctor import main as doctor

    doctor(_settings(args), None if args.no_write else "docs/live_status.json")


def cmd_call(args) -> None:
    """Live silent call: bridge up -> (create agent if needed) -> Bolna calls the contact -> glasses answer."""
    from .agent import Bolna, build_agent_spec
    from .bridge import serve
    from .decoder import JsonlDecoder

    s = _settings(args)
    missing = [k for k, v in (("BOLNA_API_KEY", s.bolna_api_key), ("SETU_PUBLIC_URL", s.public_url),
                              ("SETU_BRIDGE_TOKEN", s.bridge_token)) if not v]
    if missing:
        sys.exit("set " + ", ".join(missing) + " in .env (see .env.example)")
    if args.contact not in s.contacts:
        sys.exit(f"no number for {args.contact!r} in SETU_CONTACTS")
    if not s.bolna_agent_id:
        spec = build_agent_spec(s.public_url, s.bridge_token, s.language, args.voice, s.telephony, s.cartesia_voice_id)
        s.bolna_agent_id = Bolna(s.bolna_api_key).create_agent(spec)
        print(f"created agent; add to .env:  BOLNA_AGENT_ID={s.bolna_agent_id}")
    relay = _build_relay(s, not args.mute)
    serve(relay, args.port, s.bridge_token)
    sess = relay.start_call(args.contact, args.reason or f"{s.user_name} wanted to talk to their {args.contact}")
    if args.decoder:
        for u in JsonlDecoder(args.decoder, follow=True).utterances():
            relay.on_utterance(u)
            if relay.active is None:
                break
    else:
        print("no --decoder: answer questions by typing a phrase (e.g. 'yes'), Ctrl+C to stop")
        from .decoder import Hypothesis, Utterance
        try:
            while relay.active is not None:
                text = input("> ").strip()
                if text:
                    relay.on_utterance(Utterance(time.time(), [Hypothesis(text, 1.0)]))
        except (KeyboardInterrupt, EOFError):
            pass
    if sess.execution_id and relay.bolna:
        ex = relay.bolna.get_execution(sess.execution_id)
        Path("calls").mkdir(exist_ok=True)
        f = Path("calls") / f"{sess.execution_id}.json"
        f.write_text(json.dumps({"execution": ex, "events": sess.log}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"status {ex.get('status')}; transcript + events -> {f}")


def cmd_check_secrets(args) -> None:
    from .secrets_scan import scan

    hits = scan(Path(args.root))
    for h in hits:
        print(h)
    if hits:
        sys.exit(f"{len(hits)} possible secret(s) or private file(s): fix before pushing")
    print("no secrets or private files found")


def cmd_replay(args) -> None:
    """Feed recorded recogniser outputs (JSONL) through the relay, outside a call; scores them if they carry truth."""
    import json as _json

    from .decoder import parse_line
    from .relay import Relay
    from .voice import Speaker

    s = _settings(args)
    relay = Relay(s, Speaker(s, play=False), min_confidence=args.min_confidence)
    n = acted = right = scored = 0
    for line in Path(args.file).read_text(encoding="utf-8").splitlines():
        u = parse_line(line)
        if u is None:
            continue
        truth = _json.loads(line).get("truth")
        c = relay.on_utterance(u)
        n += 1
        if c.phrase is not None:
            acted += 1
            if truth is not None:
                scored += 1
                right += c.phrase == truth
    print(f"\n{n} utterances, acted on {acted}" + (f", correct when acting {right}/{scored} = {right / scored:.0%}"
                                                   if scored else ""))


def cmd_label(args) -> None:
    from .datasets import label
    from .voice import Deepgram, Sarvam

    s = _settings(args)
    dg = Deepgram(s.deepgram_api_key) if s.deepgram_api_key else None
    sv = Sarvam(s.sarvam_api_key) if s.sarvam_api_key else None
    if not (dg or sv):
        sys.exit("set DEEPGRAM_API_KEY and/or SARVAM_API_KEY")
    for f in args.files:
        r = label(f, s.language, dg, sv)
        print(f"{f}: accepted={r['accepted']} disagreement={r.get('disagreement')}  "
              + " | ".join(f"{k}: {v['transcript'][:60]}" for k, v in r["providers"].items()))


def cmd_prompts(args) -> None:
    from .datasets import tts_prompts
    from .voice import Speaker

    s = _settings(args)
    lines = [l.strip() for l in Path(args.sentences).read_text(encoding="utf-8").splitlines() if l.strip()]
    m = tts_prompts(lines[: args.limit], args.out, Speaker(s, play=False), s.language)
    print(f"{len(m['prompts'])} prompts -> {args.out}/manifest.json")


def cmd_translate_phrases(args) -> None:
    from .datasets import translate_lines
    from .phrases import DATA, PHRASES
    from .voice import Sarvam

    s = _settings(args)
    if not s.sarvam_api_key:
        sys.exit("set SARVAM_API_KEY")
    out = translate_lines([p.en for p in PHRASES], Sarvam(s.sarvam_api_key), args.lang)
    DATA.mkdir(exist_ok=True)
    f = DATA / f"phrases_{args.lang}.json"
    f.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {f}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="setu", description="Setu Glasses: silent speech -> voice agent")
    ap.add_argument("--env", default=".env")
    sub = ap.add_subparsers(dest="cmd", required=True)
    langs = sorted(LANGUAGES)

    p = sub.add_parser("phrases"); p.add_argument("--lang", choices=langs); p.set_defaults(fn=cmd_phrases)
    for name, fn in (("agent-spec", cmd_agent_spec), ("create-agent", cmd_create_agent)):
        p = sub.add_parser(name)
        p.add_argument("--lang", choices=langs); p.add_argument("--voice", default="auto", choices=["auto", "sarvam", "cartesia", "kalpa"])
        p.add_argument("--telephony", choices=["plivo", "exotel"]); p.add_argument("--custom-llm-url"); p.add_argument("--custom-llm-model")
        if name == "agent-spec":
            p.add_argument("--out")
        p.set_defaults(fn=fn)
    p = sub.add_parser("say"); p.add_argument("text"); p.add_argument("--lang", choices=langs); p.set_defaults(fn=cmd_say)
    p = sub.add_parser("run"); p.add_argument("--decoder", required=True); p.add_argument("--port", type=int, default=8787)
    p.add_argument("--lang", choices=langs); p.add_argument("--min-confidence", type=float); p.add_argument("--mute", action="store_true")
    p.add_argument("--replay", action="store_true", help="read the file from the start instead of tailing it")
    p.set_defaults(fn=cmd_run)
    p = sub.add_parser("simulate"); p.add_argument("script"); p.add_argument("--lang", choices=langs); p.add_argument("--mute", action="store_true")
    p.set_defaults(fn=cmd_simulate)
    p = sub.add_parser("doctor"); p.add_argument("--no-write", action="store_true"); p.set_defaults(fn=cmd_doctor)
    p = sub.add_parser("call"); p.add_argument("contact"); p.add_argument("--reason"); p.add_argument("--decoder")
    p.add_argument("--lang", choices=langs); p.add_argument("--voice", default="auto", choices=["auto", "sarvam", "cartesia", "kalpa"])
    p.add_argument("--port", type=int, default=8787); p.add_argument("--mute", action="store_true"); p.set_defaults(fn=cmd_call)
    p = sub.add_parser("check-secrets"); p.add_argument("--root", default="."); p.set_defaults(fn=cmd_check_secrets)
    p = sub.add_parser("replay"); p.add_argument("file"); p.add_argument("--lang", choices=langs)
    p.add_argument("--min-confidence", type=float, default=0.7); p.set_defaults(fn=cmd_replay)
    p = sub.add_parser("label"); p.add_argument("files", nargs="+"); p.add_argument("--lang", choices=langs); p.set_defaults(fn=cmd_label)
    p = sub.add_parser("prompts"); p.add_argument("sentences"); p.add_argument("--out", required=True)
    p.add_argument("--lang", choices=langs); p.add_argument("--limit", type=int, default=60); p.set_defaults(fn=cmd_prompts)
    p = sub.add_parser("translate-phrases"); p.add_argument("--lang", required=True, choices=langs); p.set_defaults(fn=cmd_translate_phrases)
    args = ap.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
