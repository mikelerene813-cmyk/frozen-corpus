#!/usr/bin/env python3
"""Generate the synthetic board once. The output is committed and frozen; this
script only exists so you can see where the fixture came from."""
import datetime as dt, json, os, random, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from examples.freight.board import eta_hours

random.seed(395)
now = dt.datetime.fromisoformat("2026-03-14T02:00:00")
rows = []
for i in range(200):
    miles = round(random.uniform(40, 1400), 1)
    drive_left = round(random.uniform(0.5, 11.0), 2)
    plan_h = eta_hours(miles, drive_left) + random.choice([random.uniform(-4, 0), random.uniform(0, 2), random.uniform(2, 14), random.uniform(2, 14), random.uniform(2, 14)])
    appt = now + dt.timedelta(hours=max(plan_h, 1.0))
    rows.append({"id": f"L-{7000 + i}", "miles_left": miles,
                 "drive_left_h": drive_left,
                 "appt_latest": appt.replace(microsecond=0).isoformat()})
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "loads.json")
with open(out, "w", encoding="utf-8") as fh:
    json.dump(rows, fh, indent=1)
print(f"wrote {len(rows)} loads to {out}")
