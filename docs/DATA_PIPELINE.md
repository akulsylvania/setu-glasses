# Multilingual data engine

The recogniser improves with data: word error fell from 97% to 44% as training sessions went from
4 to 22 ([RESULTS.md](RESULTS.md)). Recording is cheap, because anyone can wear the glasses and read. Labelling is the
bottleneck, and doubly so in Indian languages. The partner speech APIs remove it.

## 1. Voiced sessions → word-timed labels (Deepgram + Sarvam)

The wearer reads prompts aloud while the glasses record the lip sensors, audio and video. The audio is transcribed
twice:

```bash
setu label sessions/hi_s01.wav --lang hi      # -> sessions/hi_s01.stt.json
```

* **Deepgram Nova-3** (`language=multi` for code-switched speech): word-level timestamps.
* **Sarvam Saaras v4**: transcript + phrase-level timestamps, strongest on Indian languages.
* **Agreement check:** a session is accepted only if the two transcripts agree within 25% word edit
  distance (`datasets.edit_ratio`). Disagreements are dropped or reviewed. Our in-house labeller applies the same
  rule to its prompt-vs-transcript check.

The timestamps put words onto the sensor clock, and the private training pipeline turns them into
phone-level targets.

## 2. Silent sessions → TTS-paced prompts (Sarvam / Cartesia)

Silent mouthing has no audio to transcribe. So each prompt is first played with TTS, and the
wearer mouths it in rhythm with the voice. The TTS duration and timing give approximate labels:

```bash
setu prompts samples/reading_prompts_en.txt --out prompts/en --lang en
setu prompts prompts_hi.txt --out prompts/hi --lang hi     # Sarvam Bulbul, Hindi
```

Output: `prompt_XXXX.wav` + `manifest.json` (text, provider, duration).

## 3. New languages → Sarvam Translate

```bash
setu translate-phrases --lang ta      # setu/data/phrases_ta.json
```

The phrase set and reading prompts are translated, then voiced with Bulbul in the same language. A
native speaker reviews them before recording.

## Throughput target

One wearer reading for 1 hour produces about 500 labelled sentences at an API cost of a few
dollars. That's the lever the scaling curve says we need.
