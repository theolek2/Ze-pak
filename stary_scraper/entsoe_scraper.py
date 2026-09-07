#!/usr/bin/env python3
r"""
Scraper ENTSO-E Transparency Platform File Library (FMS).

Co godzinę (uruchamiany przez Task Scheduler) robi jedno sprawdzenie:
  1. pobiera Export_log_r3.csv  (jedno żądanie)
  2. porównuje max_update_time każdego pliku z zapisanym stanem (state.json)
  3. pobiera tylko pliki, które się zmieniły (równolegle, max_parallel)

Kolejka jest "implicit": plik, którego stan nie został zapisany, przy kolejnym
uruchomieniu dalej wygląda na zmieniony i zostanie pobrany ponownie.

Użycie:
  python entsoe_scraper.py            # pobierz zmienione pliki
  python entsoe_scraper.py --seed     # ustaw baseline (bez pobierania) - start "na żywo"
"""

import argparse
import csv
import io
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

TOKEN_URL = "https://keycloak.tp.entsoe.eu/realms/tp/protocol/openid-connect/token"
FMS_URL = "https://fms.tp.entsoe.eu/"
CLIENT_ID = "tp-fms-public"
TOP_LEVEL = "TP_export"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(BASE_DIR, "config.txt")
STATE_PATH = os.path.join(BASE_DIR, "state.json")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

LOG_FOLDER = "/TP_export/"
LOG_FILENAME = "Export_log_r3.csv"

RATE_LIMIT_PER_MIN = 100
REQUEST_TIMEOUT = 180


# ---------------------------------------------------------------
#  Konfiguracja
# ---------------------------------------------------------------

def load_config(path=CONFIG_PATH):
    if not os.path.exists(path):
        sys.exit(f"ERROR: nie znaleziono '{path}'.")

    cfg = {"username": None, "password": None, "max_parallel": 3, "data_items": []}

    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip().lower()
                value = value.strip()
                if key in ("username", "password"):
                    cfg[key] = value
                elif key == "max_parallel":
                    cfg[key] = int(value)
                continue
            cfg["data_items"].append(line)

    if not cfg["data_items"]:
        sys.exit("ERROR: brak instrumentów w config.txt (dodaj nazwy folderów).")
    return cfg


# ---------------------------------------------------------------
#  Stan (state.json)  ->  { "files": { "<nazwa pliku>": "<max_update_time>" } }
# ---------------------------------------------------------------

def load_state(path=STATE_PATH):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
                return data.get("files", {})
            except json.JSONDecodeError:
                print(f"WARNING: uszkodzony '{path}', zaczynam od nowa.", file=sys.stderr)
    return {}


def save_state(files, path=STATE_PATH):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump({"files": files}, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------
#  Token
# ---------------------------------------------------------------

class TokenManager:
    """Trzyma token; odświeża (logowanie) gdy wygaśnie lub dostaniemy 401."""

    def __init__(self, cfg):
        self._username = cfg["username"]
        self._password = cfg["password"]
        self._lock = threading.Lock()
        self._token = None

    def _login(self):
        if not self._username or not self._password:
            sys.exit("ERROR: brak poświadczeń w config.txt (username=/password=).")
        resp = requests.post(
            TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_id": CLIENT_ID,
                "grant_type": "password",
                "username": self._username,
                "password": self._password,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("Brak access_token w odpowiedzi Keycloak.")
        return token

    def get(self):
        with self._lock:
            if not self._token:
                self._token = self._login()
            return self._token

    def refresh(self):
        with self._lock:
            self._token = self._login()
            return self._token


# ---------------------------------------------------------------
#  Rate limiter (thread-safe) + POST do FMS
# ---------------------------------------------------------------

class RateLimiter:
    def __init__(self, max_per_min=RATE_LIMIT_PER_MIN):
        self._max = max_per_min
        self._times = []
        self._lock = threading.Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            cutoff = now - 60.0
            self._times = [t for t in self._times if t >= cutoff]
            if len(self._times) >= self._max:
                sleep_for = self._times[0] + 60.0 - now + 0.2
                time.sleep(sleep_for)
                now = time.time()
                self._times = [t for t in self._times if t >= now - 60.0]
            self._times.append(now)


_rate_limiter = RateLimiter()


def fms_post(token_manager, endpoint, body, retries=4):
    url = FMS_URL.rstrip("/") + "/" + endpoint
    for attempt in range(retries):
        token = token_manager.get()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        _rate_limiter.wait()
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException as err:
            print(f"  Błąd połączenia ({err.__class__.__name__}), próba {attempt + 1}/{retries}...",
                  file=sys.stderr)
            time.sleep(5 * (attempt + 1))
            continue
        if resp.status_code == 401:
            print("  401 - odświeżam token...", file=sys.stderr)
            token_manager.refresh()
            continue
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else 600.0
            print(f"  429 - czekam {wait:.0f}s...", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"{endpoint} HTTP {resp.status_code}: {resp.text[:500]}")
        return resp
    raise RuntimeError(f"{endpoint} nieudane po {retries} próbach.")


# ---------------------------------------------------------------
#  Log (Export_log_r3.csv)
# ---------------------------------------------------------------

def fetch_export_log(token_manager):
    """Pobiera log i zwraca listę wierszy {file_name, max_update_time}."""
    resp = fms_post(token_manager, "downloadFileContent", {
        "folder": LOG_FOLDER,
        "filename": LOG_FILENAME,
        "topLevelFolder": TOP_LEVEL,
        "downloadAsZip": False,
    })

    reader = csv.DictReader(io.StringIO(resp.text), delimiter="\t")
    rows = []
    for r in reader:
        name = (r.get("file_name") or "").strip()
        updated = (r.get("max_update_time(UTC)") or "").strip()
        if name:
            rows.append({"file_name": name, "max_update_time": updated})
    return rows


# ---------------------------------------------------------------
#  Mapowanie nazwy pliku na folder / instrument
# ---------------------------------------------------------------

_DATE_PREFIX = re.compile(r"^\d{4}_\d{2}(?:_\d{2})?_")


def filename_to_folder(filename):
    name = filename[:-4] if filename.lower().endswith(".csv") else filename
    return _DATE_PREFIX.sub("", name)


def normalize_filename(filename):
    return filename if filename.lower().endswith(".csv") else filename + ".csv"


# ---------------------------------------------------------------
#  Pobieranie pliku (streaming na dysk)
# ---------------------------------------------------------------

def download_file(token_manager, folder, filename, out_dir):
    resp = fms_post(token_manager, "downloadFileContent", {
        "folder": f"/{TOP_LEVEL}/{folder}/",
        "filename": filename,
        "topLevelFolder": TOP_LEVEL,
        "downloadAsZip": False,
    })

    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, filename)
    with open(out_path, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=1024 * 1024):
            fh.write(chunk)
    return out_path, os.path.getsize(out_path)


# ---------------------------------------------------------------
#  Main
# ---------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scraper ENTSO-E File Library.")
    parser.add_argument("--seed", action="store_true",
                        help="ustaw baseline wg logu bez pobierania (start 'na żywo')")
    parser.add_argument("--config", default=CONFIG_PATH, help="ścieżka do config.txt")
    args = parser.parse_args()

    cfg = load_config(args.config)
    data_items = set(cfg["data_items"])
    max_parallel = cfg["max_parallel"]

    files_state = load_state()
    token_manager = TokenManager(cfg)

    print("Pobieram log exportów...", flush=True)
    log_rows = fetch_export_log(token_manager)

    # Dopasuj log do skonfigurowanych instrumentów i wyznacz zmienione pliki.
    changed = []
    seen = 0
    for row in log_rows:
        folder = filename_to_folder(row["file_name"])
        if folder not in data_items:
            continue
        filename = normalize_filename(row["file_name"])
        updated = row["max_update_time"]
        seen += 1
        if args.seed:
            files_state[filename] = updated
        elif files_state.get(filename) != updated:
            changed.append({"folder": folder, "filename": filename, "updated": updated})

    print(f"W logu znaleziono {seen} plików dla Twoich instrumentów.", flush=True)

    if args.seed:
        save_state(files_state)
        print("Baseline ustawiony (state.json) - bez pobierania.", flush=True)
        return

    if not changed:
        save_state(files_state)
        print("Brak zmian od ostatniego uruchomienia.", flush=True)
        return

    print(f"Do pobrania: {len(changed)} plików (równolegle x{max_parallel}).", flush=True)

    def work(item):
        return item, download_file(token_manager, item["folder"], item["filename"],
                                   os.path.join(OUTPUT_DIR, item["folder"]))

    downloaded = 0
    with ThreadPoolExecutor(max_workers=max_parallel) as pool:
        futures = [pool.submit(work, item) for item in changed]
        for future in as_completed(futures):
            item, (out_path, size) = future.result()
            files_state[item["filename"]] = item["updated"]
            save_state(files_state)
            downloaded += 1
            print(f"  [{downloaded}/{len(changed)}] {item['filename']} ({size} B)", flush=True)

    save_state(files_state)
    print(f"Zakończono: pobrano {downloaded} plików.", flush=True)


if __name__ == "__main__":
    main()
