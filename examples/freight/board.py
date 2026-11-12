"""A second judgment system for the harness: can this truckload still deliver on time?

Every row is one load in transit on a synthetic board. For each one the function
answers the question a night dispatcher answers all shift: given the miles left,
the driver's remaining hours of service, and the delivery appointment, will this
load make it, and what is the honest sentence explaining why?

The hours-of-service math uses the public property-carrying limits (49 CFR 395.3):
11 hours of driving, then a 10-hour off-duty break. Everything else (speeds,
miles, appointments) is synthetic. No carrier's data is in here.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Dict, Mapping

AVG_MPH = 50.0            # planning speed, including traffic and fuel stops
BREAK_HOURS = 10.0        # required off-duty reset once driving hours run out
MAX_DRIVE_HOURS = 11.0    # driving allowed after a full reset
AT_RISK_SLACK_H = 2.0     # less cushion than this and somebody should look


def eta_hours(miles: float, drive_left_h: float) -> float:
    """Hours from now until arrival, inserting 10-hour breaks where the clock runs out."""
    hours_needed = miles / AVG_MPH
    elapsed = 0.0
    available = drive_left_h
    while hours_needed > available:
        elapsed += available + BREAK_HOURS
        hours_needed -= available
        available = MAX_DRIVE_HOURS
    return elapsed + hours_needed


def check_load(row: Mapping[str, Any], now: dt.datetime) -> Dict[str, Any]:
    appt = dt.datetime.fromisoformat(row["appt_latest"])
    window_h = (appt - now).total_seconds() / 3600.0
    eta_h = eta_hours(row["miles_left"], row["drive_left_h"])
    slack = round(window_h - eta_h, 2)
    needs_break = eta_h > row["drive_left_h"] + 1e-9

    if slack < 0:
        status = "late"
        why = (f"Projected {abs(slack):.1f} h past the appointment"
               + (" even before the required 10-hour break is counted. " if not needs_break
                  else " once the required 10-hour break is counted. ")
               + "Call the receiver now and look for a recovery driver.")
    elif slack < AT_RISK_SLACK_H:
        status = "at_risk"
        why = (f"Only {slack:.1f} h of cushion"
               + (" with a 10-hour break in the plan." if needs_break else ".")
               + " One slow stretch and it misses.")
    else:
        status = "on_time"
        why = f"{slack:.1f} h of cushion. Nothing to do yet."

    return {"status": status, "slack_h": slack, "eta_h": round(eta_h, 2),
            "needs_break": needs_break, "why": why}
