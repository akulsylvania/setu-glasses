# Results

All numbers come from our own recordings with the Setu glasses. **Every model is tested on sessions it
never trained on**: the glasses are taken off and put back on between sessions, which is the hard, honest setting.

Metrics (lower is better), corpus-level edit distance divided by reference length:
* **WER**: word error rate
* **CER**: character error rate
* **SER**: sentence error rate (the share of sentences not exactly right)

## 1. Sentence-level silent speech decoding

| Dataset | Sessions | Utterances | Words | Speech |
|---|---|---|---|---|
| All paired recordings (2 people) | 39 | 1,638 read sentences + 107 free-talk segments | ~12,700 read + ~1,300 free | ~1.6 h of speech, ~2 h recorded |
| of which never-repeated everyday sentences | 10 | 550 | 4,861 | 31 min |
| Test set A: held-out sessions | 4 | 179 sentences | 1,270 words (6,372 characters) | |
| Test set B: held-out sessions, sentences never seen in training | 2 | 119 sentences | 1,084 words (5,820 characters) | |

Test sets are whole sessions held out from training, never single sentences, so every number
below is on new wearings. Error rates are pooled over every word and character in the test set, not
averaged per sentence. The model decodes in two ways:
* **open**: a word lexicon + a trigram language model
* **known list**: picks the most likely sentence from the list of prompts we recorded

### Test set A: sentences that also appear in training sessions (new wearings)

| Model | WER (known list) | SER (known list) | CER (known list) | WER (open) | CER (open) |
|---|---|---|---|---|---|
| **Best model** | **34.9%** | **39.1%** (61% of sentences exactly right) | **28.9%** | **55.0%** | 44.0% |
| Mean of 3 training seeds | 42.5% | 45.4% | 34.0% | 57.0% | 44.5% |

### WER as training data grows

Same test set A, same model, trained on the first N sessions:

| Training sessions | 4 | 8 | 12 | 16 | 22 |
|---|---|---|---|---|---|
| WER (known list) | 96.7% | 84.0% | 67.0% | 56.9% | **43.5%** |
| WER (open) | 88.5% | 89.8% | 75.3% | 65.0% | **57.0%** |
| Sentences exactly right (known list) | 3% | 14% | 31% | 41% | **53%** |

Known-list WER falls from 97% to 44% as training goes from 4 to 22 sessions, and it's still falling
steeply, so we haven't hit the limit of the approach.

### Test set B: sentences never seen in training

Test set B: 2 held-out sessions, 119 sentences / 1,084 words from the never-repeated pool, decoded
against a 6.4k-word lexicon and a trigram LM built without the pool (known list = 3,828-sentence pool).

| Training data (mean of 2 seeds) | WER (known list) | WER (open) |
|---|---|---|
| Earlier sessions (repeated prompts) | 99.6% | 97.7% |
| + 1 hour of never-repeated sentences | **93.1%** | **94.7%** |

Brand-new sentences are the frontier. One hour of never-repeated sentences is what started to move them.
Data diversity is the lever. The pipeline and roadmap are in [RESEARCH.md](RESEARCH.md), and the multilingual
data engine in [DATA_PIPELINE.md](DATA_PIPELINE.md).

## 2. Product phrase set (v1)

The product vocabulary is the 20 phrases + "stay still" in [`setu/phrases.py`](../setu/phrases.py). Phrase
recognition is a much easier task than the sentence decoding above: picking 1 of 21 classes, with
whole-phrase training examples. v1 phrase recordings are in progress, and held-out phrase accuracy will be
reported here with the same session-level protocol.

## Known limitations

* Mostly one speaker; the second person appears only in the sentence-level data.
* Sensor position shifts between wearings; a rigid mount is the next hardware revision.
