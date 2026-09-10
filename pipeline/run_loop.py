#!/usr/bin/env python3
"""Pętla 30-min: dlt -> dbt -> MotherDuck (append) -> Lightdash (live query).

Użycie:
  python pipeline/run_loop.py --once --tables fct_pse_cor   # lekki test 1 obiegu
  python pipeline/run_loop.py --once                        # 1 pełny obieg
  python pipeline/run_loop.py                               # nieskończona pętla co 30 min
  python pipeline/run_loop.py --skip-dlt --skip-dbt --once --tables fct_pse_cor  # sam sync

Każdy etap działa jako osobny podproces (zamknięte koneksje do energy.duckdb),
więc nie ma blokad pliku między dlt / dbt / sync. Lightdash Cloud czyta
na żywo z MotherDuck, więc nie ma triggera odświeżania.
"""

from __future__ import annotations

import argparse
import atexit
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIPELINE_DIR = os.path.join(PROJECT_ROOT, "pipeline")
DBT_DIR = os.path.join(PROJECT_ROOT, "dbt")
LOCK_FILE = os.path.join(PIPELINE_DIR, ".loop.lock")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")

RUN_PIPELINE = os.path.join(PIPELINE_DIR, "run_pipeline.py")
SYNC_SCRIPT = os.path.join(PIPELINE_DIR, "sync_motherduck.py")


def log(msg: str, log_fh=None) -> None:
    line = f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S}Z {msg}"
    print(line, flush=True)
    if log_fh:
        log_fh.write(line + "\n")
        log_fh.flush()


def acquire_lock() -> bool:
    """Prosty lock plikowy przeciw nakładaniu się obiegów. True gdy zdobyty."""
    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
    except FileExistsError:
        return False

    def _release() -> None:
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

    atexit.register(_release)
    return True


def run_step(cmd: list[str], label: str, cwd: str, log_fh=None) -> tuple[int, str]:
    """Uruchom krok; zwroc (rc, caly output) do dalszej analizy (np. rerun dlt)."""
    log(f"[{label}] start (cwd={os.path.basename(cwd)})", log_fh)
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    dt = time.time() - t0
    output = (proc.stdout or "") + "\n" + (proc.stderr or "")
    if proc.stdout:
        for line in proc.stdout.strip().splitlines()[-12:]:
            log(f"[{label}|out] {line}", log_fh)
    if proc.returncode != 0 and proc.stderr:
        for line in proc.stderr.strip().splitlines()[-12:]:
            log(f"[{label}|err] {line}", log_fh)
    log(f"[{label}] koniec rc={proc.returncode} ({dt:.1f}s)", log_fh)
    return proc.returncode, output


def has_pending_packages(output: str) -> bool:
    """Czy dlt zglosil zalegle paczki (swieze dane NIE wyekstrahowane)?"""
    text = output.lower()
    return ("pending load packages" in text) or ("will not be extracted" in text)


def run_dlt_step(py: str, args, log_fh=None) -> bool:
    """dlt z auto-rerunem gdy poprzedni run zostawil zalegle paczki (np. po killu)."""
    attempts = 1 + max(int(args.dlt_retries), 0)
    for n in range(1, attempts + 1):
        rc, output = run_step([py, RUN_PIPELINE], f"dlt-{n}", PROJECT_ROOT, log_fh)
        if rc != 0:
            return False
        if has_pending_packages(output) and n < attempts:
            log(f"[dlt] wykryto zalegle paczki (proba {n}/{attempts}) - "
                f"ponawiam dlt aby dobrac swieze dane.", log_fh)
            continue
        if has_pending_packages(output):
            log("[dlt] zalegle paczki mimo rerunow - lece dalej z tym co jest.",
                log_fh)
        return True
    return True


def run_once(args, log_fh=None) -> bool:
    py = sys.executable
    ok = True

    if not args.skip_dlt:
        ok = run_dlt_step(py, args, log_fh)
        if not ok and not args.continue_on_error:
            log("Obieg przerwany po dlt.", log_fh)
            return False

    if (ok or args.continue_on_error) and not args.skip_dbt:
        rc, _ = run_step(["dbt", "run", "--profiles-dir", "."], "dbt", DBT_DIR, log_fh)
        ok = ok and rc == 0
        if rc != 0 and not args.continue_on_error:
            log("Obieg przerwany po dbt.", log_fh)
            return False

    if (ok or args.continue_on_error) and not args.skip_sync:
        cmd = [py, SYNC_SCRIPT, "--database", args.database,
               "--tables", *args.tables,
               "--overlap-days", str(args.overlap_days)]
        if args.source:
            cmd += ["--source", args.source]
        if args.force_sync:
            cmd.append("--force")
        rc, _ = run_step(cmd, "sync", PROJECT_ROOT, log_fh)
        ok = ok and rc == 0

    return ok


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, PROJECT_ROOT)
    try:
        from pipeline.sync_motherduck import CANONICAL_TABLES
    except ModuleNotFoundError:
        from sync_motherduck import CANONICAL_TABLES  # type: ignore

    parser = argparse.ArgumentParser(description="Petla 30-min: dlt -> dbt -> MotherDuck.")
    parser.add_argument("--interval", type=int, default=1800,
                        help="Odstep petli w sekundach (domyslnie 1800).")
    parser.add_argument("--once", action="store_true",
                        help="Jeden obieg i koniec (do testow).")
    parser.add_argument("--database", default="energy_lightdash_test")
    parser.add_argument("--tables", nargs="*", default=CANONICAL_TABLES)
    parser.add_argument("--source", choices=["entsoe", "pse"], default=None,
                        help="Zawez sync do zrodla: entsoe albo pse.")
    parser.add_argument("--overlap-days", type=int, default=2)
    parser.add_argument("--force-sync", action="store_true",
                        help="sync --force (pelna kopia).")
    parser.add_argument("--skip-dlt", action="store_true")
    parser.add_argument("--skip-dbt", action="store_true")
    parser.add_argument("--skip-sync", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true",
                        help="Lec dalej mimo bledu etapu.")
    parser.add_argument("--jitter", type=int, default=60,
                        help="Losowe +/- sekund do sleep (domyslnie 60).")
    parser.add_argument("--dlt-retries", type=int, default=2,
                        help="Ile razy ponowic dlt po warningu o zaleglych paczkach.")
    args = parser.parse_args(argv)

    unknown = sorted(set(args.tables) - set(CANONICAL_TABLES))
    if unknown:
        print(f"Nieznane tabele: {', '.join(unknown)}.", file=sys.stderr)
        return 2

    if not acquire_lock():
        print(f"Lock zajety ({LOCK_FILE}) - inny obieg dziala. Koniec.",
              file=sys.stderr)
        return 3

    os.makedirs(LOG_DIR, exist_ok=True)
    iteration = 0
    while True:
        iteration += 1
        t0 = time.time()
        day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(LOG_DIR, f"loop_{day}.log")
        with open(log_path, "a", encoding="utf-8") as log_fh:
            log(f"=== obieg #{iteration} start ===", log_fh)
            try:
                ok = run_once(args, log_fh)
            except Exception as exc:  # petla nie moze pasc
                log(f"=== obieg #{iteration} WYJATEK: "
                    f"{type(exc).__name__}: {str(exc)[:200]} ===", log_fh)
                ok = False
            log(f"=== obieg #{iteration} {'OK' if ok else 'BLAD'} ===", log_fh)

        if args.once:
            return 0 if ok else 1

        elapsed = time.time() - t0
        sleep_for = max(args.interval - elapsed + random.uniform(-args.jitter, args.jitter), 30)
        log(f"Sleep {sleep_for:.0f}s do nastepnego obiegu...")
        time.sleep(sleep_for)


if __name__ == "__main__":
    raise SystemExit(main())
