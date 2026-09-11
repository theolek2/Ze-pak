#!/usr/bin/env python3
"""Status backfillu / pipeline bez dotykania bazy i API (tylko logi).

Uzycie:
  python pipeline/backfill_status.py
  python pipeline/backfill_status.py --log logs/backfill_2025_2026.log
"""

from __future__ import annotations

import argparse
import os
import re
from collections import Counter
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Oczekiwane pliki 2025-2026 per zasob (jak w .opencode check 11.09: 21 na instrument).
EXPECTED = {
    "energy_prices": 0,  # pelna historia juz lokalnie - pomijane w backfillu
    "imbalance_prices": 21,
    "generation_forecasts": 21,
    "aggregated_generation": 21,
}

TS_RE = re.compile(r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\]")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Status backfillu z logow.")
    ap.add_argument("--log", default=os.path.join(PROJECT_ROOT, "logs", "backfill_2025_2026.log"))
    args = ap.parse_args(argv)

    out_log = args.log.replace(".log", ".dlt-backfill.out.log")
    started = Counter()
    done = Counter()
    done_rows = Counter()
    last = None
    if os.path.exists(out_log):
        with open(out_log, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                m = re.search(r"\[entsoe:([^\]]+)\] pobieram (\S+)", line)
                if m:
                    started[m.group(1)] += 1
                    last = (m.group(1), m.group(2))
                    continue
                m = re.search(r"\[entsoe:([^\]]+)\] gotowe \S+ \((\d+) wierszy", line)
                if m:
                    done[m.group(1)] += 1
                    done_rows[m.group(1)] += int(m.group(2))

    t0 = None
    stages = []
    if os.path.exists(args.log):
        with open(args.log, encoding="utf-8", errors="ignore") as fh:
            for line in fh:
                m = TS_RE.search(line)
                ts = m.group(1) if m else None
                if "START dlt-backfill" in line and ts and t0 is None:
                    t0 = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                if "KONIEC" in line or "DONE" in line:
                    stages.append(line.strip())

    total_exp = sum(EXPECTED.values())
    total_started = sum(started.values())
    total_done = sum(done.values())
    print(f"START: {t0} | pliki: start={total_started}/{total_exp}, "
          f"gotowe={total_done}/{total_exp}")
    for res, exp in EXPECTED.items():
        if exp == 0:
            continue
        print(f"  {res}: start={started.get(res, 0)}/{exp} "
              f"gotowe={done.get(res, 0)}/{exp} "
              f"wierszy={done_rows.get(res, 0)}")
    if last:
        print(f"  ostatni plik: [{last[0]}] {last[1]}")
    if t0 and total_started:
        mins = (datetime.now() - t0).total_seconds() / 60
        rate = total_started / max(mins, 0.1)
        left = max(total_exp - total_started, 0)
        print(f"  tempo ~{rate:.1f} pliku/min -> ETA ~{left / max(rate, 0.01):.0f} min "
              f"(sam download; +parse/dbt/sync)")
    for s in stages[-4:]:
        print(f"  {s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
