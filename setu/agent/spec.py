"""Bolna agent definition for the Setu relay agent.

The agent speaks on the wearer's behalf in a phone call. Whenever the other person asks the wearer
something, the agent calls the `ask_user` custom function: the question goes to the glasses (spoken
into the earpiece), the wearer answers silently, and the function returns the sentence to say.

Partner stack per language (all switchable):
    telephony    Plivo (default) or Exotel
    transcriber  Deepgram Nova-3 for English, Sarvam Saaras v4 for Indian languages
    synthesizer  Cartesia Sonic (wearer's own voice, English), Sarvam Bulbul v3 (11 Indian languages),
                 Kalpa Labs (Hinglish)
    llm          OpenAI via Bolna, or any OpenAI-compatible endpoint (Sarvam, Simplismart) as custom LLM
"""

from __future__ import annotations

from ..config import LANGUAGES

SYSTEM_PROMPT = """You are Setu, a voice relay speaking on behalf of {{user_name}}, who cannot speak out loud right now
and is answering through silent-speech glasses. Your session id is {{session_id}}.

Rules:
- You only relay. Never answer for {{user_name}} from your own knowledge and never make up their reply.
- Whenever the other person asks {{user_name}} anything or needs a decision, call ask_user with the question,
  then say the returned "say" text, naturally, in the first person on their behalf ("{{user_name}} says ...").
- If ask_user returns status "pending", tell the other person {{user_name}} is still answering, then call
  get_user_answer. If it returns status "none", ask the other person to repeat or rephrase as a yes/no question.
- Encourage yes/no questions: they are fastest for {{user_name}} to answer.
- Keep every turn short. Speak {{language_name}}.
- Context for this call: {{call_reason}}"""

WELCOME = "{{opening_line}}"


def _tool(name: str, description: str, url: str, token: str, props: dict, pre_call: str | None = None) -> dict:
    t = {"name": name, "description": description,
         "parameters": {"type": "object", "properties": props, "required": list(props)},
         "key": "custom_task",
         "value": {"method": "POST", "url": url, "api_token": f"Bearer {token}",
                   "headers": {"Content-Type": "application/json"},
                   "param": {k: f"%({k})s" for k in props}}}
    if pre_call:
        t["pre_call_message"] = pre_call
    return t


def relay_tools(public_url: str, token: str) -> list[dict]:
    session = {"type": "string", "description": "The session id from your instructions."}
    return [
        _tool("ask_user", "Call this whenever the other person asks the wearer a question or needs their decision. "
              "Pass the question in short, plain words, ideally as a yes/no question.",
              f"{public_url}/bolna/ask_user", token,
              {"question": {"type": "string", "description": "The question for the wearer."}, "session": session},
              pre_call="Let me ask them."),
        _tool("get_user_answer", "Call this after ask_user returned status pending, to fetch the wearer's answer.",
              f"{public_url}/bolna/get_user_answer", token, {"session": session}),
    ]


def synthesizer(lang: str, voice: str = "auto", cartesia_voice_id: str | None = None) -> dict:
    if voice == "auto":
        voice = "cartesia" if lang == "en" and cartesia_voice_id else "sarvam"
    if voice == "cartesia":
        cfg = {"provider": "cartesia", "provider_config": {"voice": "Setu wearer", "voice_id": cartesia_voice_id,
                                                           "model": "sonic-3.5", "language": lang}}
    elif voice == "kalpa":
        cfg = {"provider": "kalpa", "provider_config": {"voice": "Arjun", "model": "kalpa-tts-1"}}
    else:
        cfg = {"provider": "sarvam", "provider_config": {"voice": "Shubh", "voice_id": "shubh",
                                                         "model": "bulbul:v3", "language": lang, "speed": 1.0}}
    return cfg | {"stream": True, "buffer_size": 250, "audio_format": "wav"}


def transcriber(lang: str) -> dict:
    if lang == "en":
        return {"provider": "deepgram", "model": "nova-3", "language": "en", "stream": True,
                "encoding": "linear16", "sampling_rate": 16000, "endpointing": 300}
    return {"provider": "sarvam", "model": "saaras:v4", "language": lang, "stream": True, "endpointing": 500,
            "context": "Phone call relayed for a person who answers through silent-speech glasses."}


def llm_config(custom_base_url: str | None = None, custom_model: str | None = None) -> dict:
    if custom_base_url and custom_model:
        return {"provider": "custom", "base_url": custom_base_url.rstrip("/"), "model": custom_model,
                "family": "llama", "max_tokens": 150, "temperature": 0.2}
    return {"provider": "openai", "model": "gpt-5.4-mini", "max_tokens": 150, "temperature": 1}


def build_agent_spec(public_url: str, bridge_token: str, lang: str = "en", voice: str = "auto",
                     telephony: str = "plivo", cartesia_voice_id: str | None = None,
                     custom_llm_url: str | None = None, custom_llm_model: str | None = None,
                     name: str | None = None) -> dict:
    if lang not in LANGUAGES:
        raise ValueError(f"unsupported language {lang!r}; choose from {sorted(LANGUAGES)}")
    if telephony not in ("plivo", "exotel"):
        raise ValueError("telephony must be plivo or exotel")
    public_url = public_url.rstrip("/")
    tools = relay_tools(public_url, bridge_token)
    task = {
        "task_type": "conversation",
        "tools_config": {
            "llm_agent": {"agent_type": "simple_llm_agent", "agent_flow_type": "streaming",
                          "llm_config": llm_config(custom_llm_url, custom_llm_model)},
            "synthesizer": synthesizer(lang, voice, cartesia_voice_id),
            "transcriber": transcriber(lang),
            "input": {"provider": telephony, "format": "wav"},
            "output": {"provider": telephony, "format": "wav"},
            "api_tools": {"tools": tools, "tools_params": {t["name"]: t["value"] for t in tools}},
        },
        "toolchain": {"execution": "parallel", "pipelines": [["transcriber", "llm", "synthesizer"]]},
        "task_config": {"hangup_after_silence": 30, "call_terminate": 600},
    }
    return {
        "agent_config": {"agent_name": name or f"Setu relay ({LANGUAGES[lang]})",
                         "agent_welcome_message": WELCOME,
                         "webhook_url": f"{public_url}/bolna/webhook",
                         "call_summary_enabled": True,
                         "tasks": [task]},
        "agent_prompts": {"task_1": {"system_prompt": SYSTEM_PROMPT}},
    }
