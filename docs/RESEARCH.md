# Long-term track: sentence-level silent speech

The product ships with a closed phrase set because that's what works reliably today. The long-term
goal is **open-vocabulary silent speech**: mouth any sentence, in any of our languages, and Setu
decodes it. This is a data problem as much as a model problem, so most of our effort so far went into
a capture-and-label pipeline that turns ordinary reading sessions into training data.

## 1. Data stream pipeline (what we have built and used so far)

```
            ┌─────────────── one recording session (wearer reads prompts aloud) ───────────────┐
 glasses ─► │ lip-sensor streams (device clock)                                                 │
 mic     ─► │ audio, 48 kHz, per-block host timestamps                                          │
 webcam  ─► │ video, 720p / 30 fps, per-frame host timestamps                                   │
            └──────────────────────────────────────┬───────────────────────────────────────────┘
                                                   ▼
   1. clock alignment: sensor, audio and video on one timeline; sync bursts at start and end as a check
   2. speech-to-text: word-timed transcript (local Whisper today; Deepgram + Sarvam in setu/datasets.py)
   3. prompt matching: keep a sentence only if the transcript agrees with the prompt within 25% word edits
   4. phonetic labels: words → phones (pronunciation dictionary + phoneme recogniser) → frame-level targets
   5. video track: face landmarks + mouth crops per frame, lip aperture/width; camera-lag estimate
   6. dataset build: per-session normalised sensor features + phone targets; fixed session-level splits
                                                   ▼
   7. training on cloud GPUs: phone-level sequence model with frame-level auxiliary targets
   8. evaluation: held-out sessions (re-worn glasses), sentence-disjoint tests, no-input controls
```

**Prompt corpora:**
* standard read sentences
* a phoneme-rich set (60 sentences covering English phones)
* a **diverse pool of 3,828 everyday sentences** (6,404 distinct words) that are never repeated across sessions
* free-talk segments

**Data so far:**
* about 2 hours recorded (~1.6 h of speech), from 2 people
* 39 sessions
* 1,638 read sentences (~12,700 words, 1,907 distinct words) + 107 free-talk segments
* 550 of the sentences (4,861 words) from the never-repeated pool

The video stream serves two purposes:
* **Quality control:** checking whether the sensors saw the lips in a given session
* **A future teacher signal:** a pretrained visual speech-recognition model on the mouth crops can label sessions, including silent ones that have no audio.

## 2. Results so far (honest)

| Test (held-out wearings) | WER | Sentences exactly right |
|---|---|---|
| Sentences also seen in training, decoded against the known list (best model) | **34.9%** | **61%** |
| Same, open decoding (lexicon + trigram LM) | 55.0% | |
| Sentences never seen in training, known list of 3,828 | 92–94% | |

| Training sessions | 4 | 8 | 12 | 16 | 22 |
|---|---|---|---|---|---|
| WER (known list) | 97% | 84% | 67% | 57% | **44%** |

* WER keeps dropping steeply with more sessions: data is the lever.
* Brand-new sentences are where the work is. One hour of never-repeated sentences cut their WER by 3 to 6 points, which is the clearest signal of what to do next.

**Tried and dropped** (each tested against the same held-out benchmark):

| Idea | Outcome |
|---|---|
| Viseme (mouth-shape) targets instead of phones | worse on every metric; phones carry more training signal |
| Pretraining on a public silent-speech dataset from a different sensor type | no transfer to our sensors |
| Synthesising sensor data from video lip landmarks | synthetic data carried no usable information |
| Audio-teacher distillation, duration targets, curriculum schedules | no gain over frame-level phone targets |

## 3. Roadmap

1. **Hardware:** a rigid sensor mount, so the lips stay in the same place across wearings. This is the largest source of session-to-session error.
2. **Scale data:** hours of never-repeated sentences, then more speakers. Recruit readers through the
   care pilot, where every user's sessions also personalise their own model.
3. **Silent sessions:** TTS-paced prompts (Sarvam / Cartesia) give timing labels when there's no audio.
4. **Hindi and Indian languages:** the same pipeline with Sarvam Saaras / Deepgram multilingual labels and Bulbul-paced prompts.
5. **Per-wearer calibration:** a short calibration step at the start of each wearing, plus adapting the model to that session.
6. **Video teacher:** pseudo-labels from visual speech recognition on the mouth crops.
7. **Decoding:** language model + lexicon on top of phone posteriors. The closed list → open list path is already measured above.

Each step moves the product from 20 phrases to larger phrase packs, then sentence completion, then open vocabulary.
