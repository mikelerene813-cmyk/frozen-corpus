#!/usr/bin/env python3
"""Prove the harness can fail.

A regression suite nobody has ever seen go red is a suite nobody should trust. The
usual way one dies is quiet: the fixture stops loading, every record vanishes, and
nothing-differs-from-nothing reports OK for months.

So the first thing this repo's own tests do is break things on purpose and check
that each break is caught.

    python3 tests/test_falsifiable.py
"""
from __future__ import annotations

import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from frozencorpus import Corpus, Snapshot, compare           # noqa: E402
from frozencorpus.harness import EmptySnapshot                # noqa: E402
from frozencorpus.freeze import no_network, NetworkBlocked, seeded, frozen_clock  # noqa: E402

ROWS = [{"id": f"R{i}", "n": i} for i in range(1, 51)]


def base(fn):
    return Corpus.from_rows(ROWS, key="id").snapshot(fn)


def check(label: str, cond: bool, detail: str = "") -> bool:
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}" + (f"  — {detail}" if detail and not cond else ""))
    return cond


def main() -> int:
    ok = True
    print("breaking things on purpose:\n")

    # 1. A changed value is caught.
    a = base(lambda r: {"v": r["n"] * 2})
    b = base(lambda r: {"v": r["n"] * 2 + (1 if r["n"] == 7 else 0)})
    d = compare(a, b)
    ok &= check("one changed value is drift", len(d.changed) == 1 and not d.clean,
                f"got {len(d.changed)}")

    # 2. Unchanged code is clean — or the whole thing cries wolf.
    ok &= check("identical runs are clean", compare(a, base(lambda r: {"v": r["n"] * 2})).clean)

    # 3. A vanished record is drift, not a pass.
    fewer = Corpus.from_rows(ROWS[:40], key="id").snapshot(lambda r: {"v": r["n"] * 2})
    d = compare(a, fewer)
    ok &= check("ten vanished records is drift", len(d.removed) == 10 and not d.clean,
                f"removed={len(d.removed)}")

    # 4. An empty corpus raises instead of passing. THE important one.
    try:
        Corpus.from_rows([], key="id")
        ok &= check("empty corpus raises", False, "it did not")
    except EmptySnapshot:
        ok &= check("empty corpus raises", True)

    # 5. Comparing against an empty snapshot raises rather than reporting clean.
    try:
        compare(Snapshot(records={}), a)
        ok &= check("empty baseline raises", False, "it compared happily")
    except EmptySnapshot:
        ok &= check("empty baseline raises", True)

    # 6. Float noise below the rounding floor is not drift.
    c = base(lambda r: {"v": r["n"] * 2 + 1e-12})
    ok &= check("1e-12 of float noise is not drift", compare(a, c).clean)

    # 7. A baseline is not silently overwritten.
    import tempfile
    p = os.path.join(tempfile.mkdtemp(), "b.json")
    a.save(p)
    try:
        a.save(p)
        ok &= check("re-baselining needs saying out loud", False, "it overwrote silently")
    except FileExistsError:
        ok &= check("re-baselining needs saying out loud", True)
    a.save(p, overwrite=True)

    # 8. The network really is blocked.
    import socket
    try:
        with no_network():
            socket.socket().connect(("example.com", 80))
        ok &= check("no_network blocks a socket", False, "the socket opened")
    except NetworkBlocked:
        ok &= check("no_network blocks a socket", True)

    # 9. Duplicate keys are reported, not swallowed.
    dupes = Corpus.from_rows(ROWS + [{"id": "R1", "n": 999}], key="id")
    ok &= check("duplicate keys are reported", dupes.duplicate_keys == {"R1": 2},
                str(dupes.duplicate_keys))

    # 9b. The count belongs to the corpus that has the duplicates, and to no other.
    #     Written after check 9 passed against a version where the count lived on the
    #     class: building any second corpus wiped it, and check 9 never noticed
    #     because it built the duplicate-bearing corpus last. Order matters here.
    clean_after = Corpus.from_rows(ROWS, key="id")
    ok &= check("a later corpus does not rewrite an earlier one's duplicates",
                dupes.duplicate_keys == {"R1": 2} and clean_after.duplicate_keys == {},
                f"dupes={dupes.duplicate_keys} clean={clean_after.duplicate_keys}")
    #     And the other direction: build the clean corpus FIRST, the dirty one after,
    #     then snapshot the clean one. The old version stamped the dirty corpus's
    #     duplicates into the clean corpus's meta - a baseline reporting a data
    #     problem that belongs to a different corpus.
    clean_first = Corpus.from_rows(ROWS, key="id")
    Corpus.from_rows(ROWS + [{"id": "R2", "n": 999}], key="id")
    ok &= check("a clean corpus's snapshot carries no duplicate_keys",
                "duplicate_keys" not in clean_first.snapshot(lambda r: r["n"]).meta,
                str(clean_first.snapshot(lambda r: r["n"]).meta))

    # 10. The freeze helpers do what they say.
    with frozen_clock("2026-03-14T09:00:00") as now:
        ok &= check("frozen_clock returns the pinned time", now.hour == 9 and now.day == 14)
    with seeded(42):
        import random
        first = random.random()
    with seeded(42):
        import random
        ok &= check("seeded() repeats", random.random() == first)

    print()
    print("ALL CHECKS PASS — the harness fails when it should" if ok
          else "SOMETHING THAT SHOULD HAVE FAILED DID NOT")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
