"""Record every answer, then diff the recordings.

The shape is deliberately boring:

    corpus   = Corpus.from_rows(rows, key="id")
    snapshot = corpus.snapshot(score_one)
    drift    = compare(Snapshot.load("baseline.json"), snapshot)

What is not boring is what `compare` refuses to do. It will not call two runs equal
because the second one was empty, and it will not let you overwrite a baseline
without saying so out loud.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple


class EmptySnapshot(RuntimeError):
    """A snapshot with no records is a bug, never a pass.

    The single most common way a regression suite goes quiet is that the fixture
    stops loading. Every record vanishes, nothing differs from nothing, and the suite
    reports OK for months. This is that failure, made loud.
    """


def _round(v: Any, places: int = 6) -> Any:
    """Floats are compared at a fixed precision, because the last bit is noise.

    Two machines, two Python builds, or one compiler flag can disagree in the
    sixteenth decimal place. A harness that treats that as drift cries wolf until
    somebody stops reading it.
    """
    if isinstance(v, float):
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Inf" if v > 0 else "-Inf"
        return round(v, places)
    if isinstance(v, dict):
        return {k: _round(x, places) for k, x in sorted(v.items())}
    if isinstance(v, (list, tuple)):
        return [_round(x, places) for x in v]
    return v


@dataclass(frozen=True)
class Corpus:
    """A fixed set of inputs, in a fixed order, with stable keys."""
    rows: Sequence[Mapping[str, Any]]
    key: str
    dupes: Mapping[Any, int] = field(default_factory=dict)

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping[str, Any]], key: str = "id") -> "Corpus":
        rows = list(rows)
        if not rows:
            raise EmptySnapshot("the corpus is empty — nothing downstream can fail")
        missing = [i for i, r in enumerate(rows) if key not in r]
        if missing:
            raise KeyError(f"rows at {missing[:5]} have no {key!r}")
        # Duplicate keys are not rejected. Real exports carry them, and pretending
        # otherwise hides a genuine data problem. They ARE reported, because keying a
        # snapshot by id silently drops all but the last of each.
        #
        # This count belongs to THIS corpus and is stored on it. An earlier version
        # parked it on the class, which meant building a second corpus silently
        # rewrote the first one's answer - and the check for this passed anyway,
        # because it happened to build the duplicate-bearing corpus last. Per-corpus
        # state, and a check that builds a clean corpus afterwards on purpose.
        seen: Dict[Any, int] = {}
        for r in rows:
            seen[r[key]] = seen.get(r[key], 0) + 1
        return cls(rows=rows, key=key,
                   dupes={k: n for k, n in seen.items() if n > 1})

    @property
    def duplicate_keys(self) -> Dict[Any, int]:
        return dict(self.dupes)

    def snapshot(self, fn: Callable[[Mapping[str, Any]], Any],
                 meta: Mapping[str, Any] | None = None) -> "Snapshot":
        """Run `fn` over every row and record what it said."""
        records: Dict[str, Any] = {}
        for row in self.rows:
            records[str(row[self.key])] = _round(fn(row))
        if not records:
            raise EmptySnapshot("the snapshot recorded nothing")
        m = {"n_rows": len(self.rows), "n_records": len(records)}
        if self.duplicate_keys:
            m["duplicate_keys"] = dict(sorted(self.duplicate_keys.items())[:50])
        m.update(meta or {})
        return Snapshot(records=records, meta=m)


@dataclass
class Snapshot:
    records: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)

    def save(self, path: str, *, overwrite: bool = False) -> None:
        """Write the snapshot. Refuses to replace an existing file unless told to.

        Re-baselining is a decision, not a side effect. A harness that regenerates
        its own baseline on every run proves only that the code agrees with itself.
        """
        if os.path.exists(path) and not overwrite:
            raise FileExistsError(
                f"{path} already exists. Re-baselining is a decision — pass "
                f"overwrite=True and say in the commit message what moved and why."
            )
        with open(path, "w", encoding="utf-8") as fh:
            json.dump({"meta": self.meta, "records": self.records}, fh,
                      indent=1, sort_keys=True, ensure_ascii=False)
            fh.write("\n")

    @classmethod
    def load(cls, path: str) -> "Snapshot":
        with open(path, encoding="utf-8") as fh:
            blob = json.load(fh)
        snap = cls(records=blob.get("records", {}), meta=blob.get("meta", {}))
        if not snap.records:
            raise EmptySnapshot(f"{path} holds no records")
        return snap


@dataclass
class Drift:
    changed: List[Tuple[str, Any, Any]]
    added: List[str]
    removed: List[str]
    meta_changed: List[Tuple[str, Any, Any]]

    @property
    def clean(self) -> bool:
        return not (self.changed or self.added or self.removed)

    def report(self, limit: int = 12) -> str:
        if self.clean:
            n = len(self.meta_changed)
            tail = f" ({n} meta field{'s' if n != 1 else ''} moved)" if n else ""
            return f"NO DRIFT{tail}"
        out = [f"DRIFT — {len(self.changed)} changed, "
               f"{len(self.added)} added, {len(self.removed)} removed"]
        for k, a, b in self.changed[:limit]:
            out.append(f"  {k}\n     was: {a!r}\n     now: {b!r}")
        if len(self.changed) > limit:
            out.append(f"  … and {len(self.changed) - limit} more")
        for k in self.added[:limit]:
            out.append(f"  + {k}")
        for k in self.removed[:limit]:
            out.append(f"  - {k}")
        return "\n".join(out)


def compare(before: Snapshot, after: Snapshot) -> Drift:
    """Diff two snapshots, key by key.

    Note what counts as drift and what does not: a changed record is drift, a vanished
    record is drift, and a new record is drift. A changed `meta` field is reported but
    is not drift on its own — corpus size and run notes are context, not output.
    """
    if not before.records or not after.records:
        raise EmptySnapshot("comparing against an empty snapshot would always pass")

    keys_b, keys_a = set(before.records), set(after.records)
    changed = [(k, before.records[k], after.records[k])
               for k in sorted(keys_b & keys_a)
               if before.records[k] != after.records[k]]
    meta_changed = [(k, before.meta.get(k), after.meta.get(k))
                    for k in sorted(set(before.meta) | set(after.meta))
                    if before.meta.get(k) != after.meta.get(k)]
    return Drift(changed=changed,
                 added=sorted(keys_a - keys_b),
                 removed=sorted(keys_b - keys_a),
                 meta_changed=meta_changed)
