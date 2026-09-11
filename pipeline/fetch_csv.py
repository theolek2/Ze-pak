#!/usr/bin/env python3
"""Proste sciaganie surowych CSV z ENTSO-E File Library + sklejanie per instrument x rok.

Bez dlt, bez bazy - czysty HTTP -> pliki. Wyjscie: export_raw/<instrument>_<rok>.csv
(miesieczne TSV sklejone, jeden naglowek).

Uzycie:
  python pipeline/fetch_csv.py --limit 1 --instruments energy_prices --years 2026  # test
  python pipeline/fetch_csv.py --years 2025 2026                                    # wszystko (84 pliki)
  python pipeline/fetch_csv.py --years 2025 2026 --workers 6

Credentiale z .dlt/secrets.toml (nigdzie nie wysylane poza Keycloak/FMS).
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import tomllib
from concurrent.futures import ThreadPoolExecutor

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from sources.entsoe.entsoe_client import (  # noqa: E402
    TokenManager,
    fetch_export_log,
    filename_to_folder,
    normalize_filename,
    download_file_content,
)
from sources.entsoe.entsoe_source import INSTRUMENTS  # noqa: E402 (foldery)

SECRETS_PATH = os.path.join(PROJECT_ROOT, ".dlt", "secrets.toml")
_print_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def load_creds():
    with open(SECRETS_PATH, "rb") as fh:
        s = tomllib.load(fh)
    return s["entsoe_username"], s["entsoe_password"]


def merge_year(cache_files: list[str], out_path: str,
               area: str | None = None) -> int:
    """Sklej pliki miesieczne w jeden (pierwszy z naglowkiem).

    area: filtr AreaMapCode (np. 'PL'); None = wszystko.
    Zwraca liczbe wierszy.
    """
    rows = 0
    with open(out_path, "w", encoding="utf-8", newline="") as out:
        for i, path in enumerate(cache_files):
            with open(path, encoding="utf-8", newline="") as fh:
                header = fh.readline().rstrip("\r\n").split("\t")
                if i == 0:
                    out.write("\t".join(header) + "\n")
                idx = header.index("AreaMapCode") if area else -1
                for line in fh:
                    if area:
                        cols = line.rstrip("\r\n").split("\t")
                        if idx >= len(cols) or cols[idx] != area:
                            continue
                    out.write(line if line.endswith("\n") else line + "\n")
                    rows += 1
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Sciaganie surowych CSV z ENTSO-E.")
    ap.add_argument("--years", nargs="+", default=["2025", "2026"])
    ap.add_argument("--instruments", nargs="*", default=None,
                    help=f"domyslnie wszystkie: {sorted(INSTRUMENTS)}")
    ap.add_argument("--out", default=os.path.join(PROJECT_ROOT, "export_raw"))
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None,
                    help="test: maks plikow per instrument x rok")
    ap.add_argument("--overwrite", action="store_true",
                    help="sciagnij od nowa mimo cache")
    ap.add_argument("--area", default=None,
                    help="filtr AreaMapCode przy sklejaniu, np. --area PL (tylko Polska)")
    ap.add_argument("--merge-only", action="store_true",
                    help="tylko sklej z cache, bez pobierania")
    args = ap.parse_args(argv)

    keys = args.instruments or sorted(INSTRUMENTS)
    unknown = sorted(set(keys) - set(INSTRUMENTS))
    if unknown:
        print(f"Nieznane instrumenty: {', '.join(unknown)}", file=sys.stderr)
        return 2
    years = {str(y) for y in args.years}

    username, password = load_creds()
    tm = TokenManager(username, password)
    if not args.merge_only:
        log("pobieram Export_log...")
        entries = fetch_export_log(tm)
        log(f"log: {len(entries)} wpisow")
    else:
        entries = []

    os.makedirs(args.out, exist_ok=True)
    cache_dir = os.path.join(args.out, "_cache")
    failed = []

    for key in keys:
        folder = INSTRUMENTS[key]["folder"]
        if args.merge_only:
            # pliki juz w cache: <cache>/<key>/*.csv
            key_dir = os.path.join(cache_dir, key)
            names = sorted(
                f for f in os.listdir(key_dir)
                if f[:4] in years
            ) if os.path.isdir(key_dir) else []
            by_year: dict[str, list[str]] = {}
            for n in names:
                by_year.setdefault(n[:4], []).append(n)
            log(f"[{key}] merge-only: {len(names)} plikow z cache")
        else:
            wanted = sorted(
                e["file_name"] for e in entries
                if filename_to_folder(e["file_name"]) == folder
                and e["file_name"][:4] in years
            )
            log(f"[{key}] {len(wanted)} plikow do sciagniecia")
            by_year = {}
            for name in wanted:
                by_year.setdefault(name[:4], []).append(name)

        def one(name: str) -> str | None:
            fname = normalize_filename(name)
            dest = os.path.join(cache_dir, key, fname)
            if os.path.exists(dest) and not args.overwrite:
                return dest
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                text = download_file_content(tm, folder, fname)
                with open(dest, "w", encoding="utf-8", newline="") as fh:
                    fh.write(text)
                mb = len(text.encode("utf-8", "ignore")) / 1048576
                log(f"[{key}] sciagnieto {fname} ({mb:.1f} MB)")
                return dest
            except Exception as exc:
                log(f"[{key}] BLAD {fname}: {type(exc).__name__}: {str(exc)[:120]}")
                failed.append(fname)
                return None

        for year in sorted(by_year):
            names = by_year[year]
            if args.limit:
                names = names[: args.limit]
            if args.merge_only:
                cached = [os.path.join(cache_dir, key, n) for n in names
                          if os.path.exists(os.path.join(cache_dir, key, n))]
            else:
                with ThreadPoolExecutor(max_workers=args.workers) as ex:
                    cached = [p for p in ex.map(one, names) if p]
            if not cached:
                log(f"[{key}] {year}: BRAK plikow (pominieto)")
                continue
            suffix = f"_{args.area}" if args.area else ""
            out_path = os.path.join(args.out, f"{key}_{year}{suffix}.csv")
            n = merge_year(cached, out_path, area=args.area)
            mb = os.path.getsize(out_path) / 1048576
            log(f"[{key}] {year}: SKLEJONO {len(cached)} plikow -> "
                f"{os.path.basename(out_path)} ({n} wierszy, {mb:.1f} MB)")

    if failed:
        print(f"FAILED ({len(failed)}): {failed}", file=sys.stderr)
        return 1
    log("DONE - wszystko sciagniete i sklejone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
