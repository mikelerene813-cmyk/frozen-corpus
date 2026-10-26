# frozen-corpus

Regression testing for systems whose output is a **judgment**.

A unit test answers *is this function right?* This answers a different question:

> **Did anything move that I did not mean to move?**

That question comes up when a system makes thousands of small judgments — a score, a
ranking, a recommendation, a refusal and the sentence explaining it — and a change
anywhere in it can quietly shift a number three screens away. You cannot assert your
way to that. You have to record what the system said, change the code, and look.

```python
from frozencorpus import Corpus, Snapshot, compare, frozen_clock, no_network, seeded

corpus = Corpus.from_rows(rows, key="id")

with no_network(), seeded(42), frozen_clock("2026-03-14T09:00:00") as now:
    snap = corpus.snapshot(lambda r: score(r, now))

drift = compare(Snapshot.load("baseline.json"), snap)
print(drift.report())        # "NO DRIFT"  or every record that moved
```

## Try it

```
python3 examples/run.py --record     # record a baseline over 240 tickets
python3 examples/run.py              # NO DRIFT
```

Now change a number in `examples/triage.py` — make `enterprise` weigh 2.1 instead of
2.0 — and run it again:

```
240 tickets scored against baseline.json
DRIFT — 24 changed, 0 added, 0 removed
  T-4004
     was: {'age_h': 60.01, 'breached': True, 'score': 9.0, 'why': 'Past SLA by 52.0 h. …'}
     now: {'age_h': 60.01, 'breached': True, 'score': 9.45, 'why': 'Past SLA by 52.0 h. …'}
  …
```

Twenty-four tickets moved. You changed one constant. That is the whole point.

## The four things that make a run repeatable

A harness is worthless if two runs of unchanged code disagree, so every source of
disagreement gets nailed down before the first baseline is recorded.

| | Why it drifts | What this does |
|---|---|---|
| **The clock** | Anything measuring an age or a deadline reads it. A corpus scored at 06:00 does not match one scored at 06:01. | `frozen_clock()` hands you one pinned `now` to pass down. |
| **The network** | A weather lookup, a geocode, a flag fetched at import — each makes the corpus a function of the day it ran. | `no_network()` raises on any socket, so the omission is an error instead of a slow-moving lie. |
| **The seed** | Sampling, shuffling, anything stochastic. | `seeded()` pins `random` and sets `PYTHONHASHSEED` for subprocesses. |
| **The fixture** | A corpus that changes under you is not a baseline. | Yours to freeze. Commit it. |

## What it refuses to do

This is most of the value, and it is all learned the hard way.

**It will not call two runs equal because the second one was empty.** The most common
way a regression suite dies is quiet — the fixture stops loading, every record
vanishes, nothing differs from nothing, and the suite reports OK for months.
`Corpus.from_rows([])` and `compare()` against an empty snapshot both raise.

**It will not overwrite a baseline by accident.** `save()` refuses an existing path
unless you pass `overwrite=True`. Re-baselining is a decision somebody makes and
writes down, not a side effect of running the tests. A harness that regenerates its
own baseline every run proves only that the code agrees with itself.

**It will not treat float noise as drift.** Values are compared at six decimal
places. Two Python builds can disagree in the sixteenth, and a harness that cries
wolf is one people stop reading.

**It will not swallow duplicate keys.** Real exports carry them. Snapshots are keyed
by id, so duplicates silently drop all but the last — `corpus.duplicate_keys` reports
them instead, and the count lands in the snapshot's `meta`.

## Prove it can fail

```
python3 tests/test_falsifiable.py
```

Thirteen deliberate breakages, each one checked to make sure it is caught: a changed
value, a vanished record, an empty corpus, an empty baseline, a silent overwrite, a
live socket, a duplicate key. **A regression suite nobody has watched go red is a
suite nobody should trust.**

```
breaking things on purpose:

  ok    one changed value is drift
  ok    identical runs are clean
  ok    ten vanished records is drift
  ok    empty corpus raises
  ok    empty baseline raises
  ok    1e-12 of float noise is not drift
  ok    re-baselining needs saying out loud
  ok    no_network blocks a socket
  ok    duplicate keys are reported
  ok    a later corpus does not rewrite an earlier one's duplicates
  ok    a clean corpus's snapshot carries no duplicate_keys
  ok    frozen_clock returns the pinned time
  ok    seeded() repeats

ALL CHECKS PASS — the harness fails when it should
```

## Where this came from

I run a night dispatch desk at a trucking company and build logistics software. The
scoring engine I work on makes tens of thousands of judgments across a board of
freight — can this truck still make that delivery, by when, and what is the honest
sentence explaining why. Every one of those is a number a dispatcher acts on at two
in the morning.

Changing one weight in that engine moves things you did not predict. This is the
pattern I use to find out what, pulled out and made general.

No dependencies. Python 3.9+. MIT.
