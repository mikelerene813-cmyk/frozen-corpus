"""A small system whose output is a judgment, used to demo the harness.

Support tickets in, a score and a sentence out. The domain does not matter; what
matters is the shape — every input produces several fields, one of them is prose,
and a change anywhere in the function can move any of them.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Mapping

TIER_WEIGHT = {"enterprise": 2.0, "business": 1.4, "free": 1.0}


def score_ticket(row: Mapping[str, Any], now: dt.datetime) -> Dict[str, Any]:
    age_h = (now - dt.datetime.fromisoformat(row["opened_at"])).total_seconds() / 3600.0
    weight = TIER_WEIGHT.get(row["tier"], 1.0)
    breached = age_h > row["sla_hours"]

    urgency = min(age_h / max(row["sla_hours"], 1), 3.0)
    score = round(urgency * weight * (1.5 if breached else 1.0), 3)

    if breached:
        over = age_h - row["sla_hours"]
        why = (f"Past SLA by {over:.1f} h. {row['tier'].title()} account, so this one "
               f"is already a conversation somebody is going to have.")
    elif urgency > 0.75:
        left = row["sla_hours"] - age_h
        why = f"{left:.1f} h left on the clock. Still recoverable without a call."
    else:
        why = "Inside the window with room. Nothing to do yet."

    return {"score": score, "breached": breached,
            "age_h": round(age_h, 2), "why": why}
