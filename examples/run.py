#!/usr/bin/env python3
"""Record a baseline, or check the current code against one.

    python3 examples/run.py --record     # first time only
    python3 examples/run.py              # every time after
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frozencorpus import Corpus, Snapshot, compare, frozen_clock, no_network, seeded  # noqa: E402
from examples.triage import score_ticket  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "tickets.json")
BASELINE = os.path.join(HERE, "baseline.json")
FROZEN_NOW = "2026-03-14T09:00:00"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true",
                    help="write a new baseline (refuses to clobber without --force)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    with open(FIXTURE, encoding="utf-8") as fh:
        rows = json.load(fh)

    corpus = Corpus.from_rows(rows, key="id")

    # Every source of run-to-run disagreement, pinned in one place.
    with no_network(), seeded(42), frozen_clock(FROZEN_NOW) as now:
        snap = corpus.snapshot(lambda r: score_ticket(r, now),
                               meta={"frozen_now": FROZEN_NOW, "seed": 42})

    if args.record:
        snap.save(BASELINE, overwrite=args.force)
        print(f"baseline written — {len(snap.records)} records")
        return 0

    drift = compare(Snapshot.load(BASELINE), snap)
    print(f"{len(snap.records)} tickets scored against {os.path.basename(BASELINE)}")
    print(drift.report())
    return 0 if drift.clean else 1


if __name__ == "__main__":
    sys.exit(main())
