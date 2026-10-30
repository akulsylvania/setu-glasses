# Partner stack

Setu uses the Symphony partner ecosystem across the whole loop, from collecting training data to
speaking for the wearer.

## In the product

| Partner | Role in Setu | Where |
|---|---|---|
| **Bolna** | Voice-agent platform: the relay agent that speaks on the wearer's behalf in calls. Outbound calls (`POST /call` with `user_data`), custom functions `ask_user` / `get_user_answer`, execution webhook, agent creation (`POST /v2/agent`) | `setu/agent/`, `setu/bridge.py`, `agents/` |
| **Plivo** (Buildathon partner) | Default telephony for the relay agent: the number your family sees | agent `input`/`output` provider |
| **Exotel** | Indian telephony alternative (`--telephony exotel`) | `agents/setu_relay.hinglish.exotel.json` |
| **Sarvam AI** | Bulbul v3 voices for 11 Indian languages (local speaker + in-call). Saaras v4 STT for Indian-language callers and for labelling Hindi and regional training sessions. Sarvam Translate for phrase packs. Sarvam-105B as an LLM option | `setu/voice/sarvam.py`, `setu/datasets.py`, agent synthesizer/transcriber |
| **Cartesia** | Sonic low-latency English TTS in the wearer's own cloned voice (`CARTESIA_VOICE_ID`) | `setu/voice/cartesia.py`, `agents/setu_relay.en.json` |
| **Deepgram** | Nova-3 streaming STT for English callers. Nova-3 pre-recorded STT with word timestamps for training-data labels (multilingual `language=multi`) | `setu/voice/deepgram.py`, `setu/datasets.py`, agent transcriber |
| **Kalpa Labs** | Hinglish (code-switched) voice for the relay agent: how many Indian families actually talk | `agents/setu_relay.hinglish.exotel.json` |
| **Simplismart** | Hosts an open model as the agent's custom LLM and for phrase re-ranking. Any OpenAI-compatible endpoint plugs in via `LLM_BASE_URL` / `--custom-llm-url` | `setu/llm.py`, `setu/agent/spec.py` |
| **OpenAI** | Default LLM of the relay agent through Bolna | agent `llm_config` |

## Next

| Partner | Role |
|---|---|
| **Truecaller for Business** | Verified caller ID ("Setu, calling on behalf of …") so relay calls aren't ignored as spam |
| **Smallest.ai** | Low-latency TTS alternative inside Bolna, for latency A/B on calls |
| **Google Cloud** | Hosting the bridge (Cloud Run) close to Bolna; Gemini as an LLM option |
| **NVIDIA Inception** | GPU credits for recogniser training |
| **Wispr Flow** | Closest consumer comparable (voice dictation). Setu is the silent input mode for the same habit; see [MARKET.md](MARKET.md) |

## Why each choice

* **Sarvam for Indian languages, Cartesia for English:** we need the same phrase to come out natively in
  Hindi or Tamil for a grandmother in Chennai, and in the wearer's own voice in English for a
  colleague. `Speaker.provider_for()` and `spec.synthesizer()` route by language.
* **Deepgram + Sarvam together for data:** labels decide what the recogniser learns. Two independent
  transcripts per session, kept only when they agree within 25% word error, give clean labels with no
  manual transcription. The same rule improved our in-house labels.
* **Bolna custom functions are what make the product work.** A phone call is a stream of questions. Turning
  every question into an `ask_user` call converts open conversation into short, closed-set answers, which
  is exactly what silent speech can deliver today.
* **Plivo / Exotel:** the wearer's family gets a normal phone call. No app is needed on the other side.
