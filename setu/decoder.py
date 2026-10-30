"""Interface between the (private) on-glasses recogniser and this public layer.

The recogniser runtime appends one JSON line per detected utterance:

    {"t": 12.84, "dur": 1.6, "top": [["i need water", 0.71], ["i am hungry", 0.12], ["(stay still)", 0.05]]}

`t` = seconds since the runtime started, `top` = the recogniser's best candidates with probabilities.
`JsonlDecoder` tails that file (follow=True, live) or replays it (follow=False, tests / offline demo).
Only these top-k phrase probabilities leave the glasses runtime; raw sensor data never does.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from .phrases import STAY_STILL


@dataclass
class Hypothesis:
    phrase: str
    prob: float


@dataclass
class Utterance:
    t: float
    hyps: list[Hypothesis]
    dur: float = 0.0

    @property
    def best(self) -> Hypothesis:
        return self.hyps[0]

    @property
    def is_reject(self) -> bool:
        return self.best.phrase == STAY_STILL


def parse_line(line: str) -> Utterance | None:
    line = line.strip()
    if not line:
        return None
    d = json.loads(line)
    hyps = sorted((Hypothesis(str(p), float(q)) for p, q in d["top"]), key=lambda h: -h.prob)
    return Utterance(float(d.get("t", 0.0)), hyps, float(d.get("dur", 0.0)))


class JsonlDecoder:
    def __init__(self, path: str | Path, follow: bool = True, poll_s: float = 0.05) -> None:
        self.path = Path(path)
        self.follow = follow
        self.poll_s = poll_s

    def utterances(self) -> Iterator[Utterance]:
        while self.follow and not self.path.exists():
            time.sleep(self.poll_s)
        with open(self.path, encoding="utf-8") as f:
            if self.follow:
                f.seek(0, 2)              # live: only utterances from now on
            while True:
                line = f.readline()
                if line:
                    u = parse_line(line)
                    if u is not None:
                        yield u
                elif self.follow:
                    time.sleep(self.poll_s)
                else:
                    return
