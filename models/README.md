# Model card: Setu phrase recogniser (weights not published)

| | |
|---|---|
| Task | Closed-set silent phrase recognition from lip motion, with a "stay still" reject class |
| Input | contactless lip-sensor features, utterance window ≤ 3.5 s |
| Output | probability per phrase → top-k JSONL ([setu/decoder.py](../setu/decoder.py)) |
| Model size | about 1.3 MB on disk; runs in real time on a laptop CPU |
| Training data | own recordings, prompted sessions, glasses re-worn between sessions |
| Evaluation | held-out sessions only (see [docs/RESULTS.md](../docs/RESULTS.md)) |
| v1 (20 phrases + reject) | recordings in progress; results will follow the protocol in docs/RESULTS.md |

The weights, training code and data are proprietary and intentionally not in this repository.
[`samples/live_format.jsonl`](../samples/live_format.jsonl) shows the recogniser's output format, which
is all the software layer consumes.
