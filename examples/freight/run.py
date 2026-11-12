#!/usr/bin/env python3
"""Check the load board's on-time judgments against the frozen baseline.

    python3 examples/freight/run.py --record     # first time only
    python3 examples/freight/run.py              # every time after
"""
from __future__ import annotations

import argparse, collections, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from frozencorpus import Corpus, Snapshot, compare, frozen_clock, no_network, seeded  # noqa: E402
from examples.freight.board import check_load  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "loads.json")
BASELINE = os.path.join(HERE, "baseline.json")
FROZEN_NOW = "2026-03-14T02:00:00"   # 2 AM: when this question actually gets asked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    with open(FIXTURE, encoding="utf-8") as fh:
        rows = json.load(fh)
    corpus = Corpus.from_rows(rows, key="id")

    with no_network(), seeded(395), frozen_clock(FROZEN_NOW) as now:
        snap = corpus.snapshot(lambda r: check_load(r, now),
                               meta={"frozen_now": FROZEN_NOW})

    counts = collections.Counter(v["status"] for v in snap.records.values())
    if args.record:
        snap.save(BASELINE, overwrite=args.force)
        print(f"baseline written: {len(snap.records)} loads {dict(counts)}")
        return 0

    drift = compare(Snapshot.load(BASELINE), snap)
    print(f"{len(snap.records)} loads checked against {os.path.basename(BASELINE)} {dict(counts)}")
    print(drift.report())
    return 0 if drift.clean else 1


if __name__ == "__main__":
    sys.exit(main())
