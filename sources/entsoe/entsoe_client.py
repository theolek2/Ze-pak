#!/usr/bin/env python3
r"""
Wspólny klient API ENTSO-E Transparency Platform File Library (FMS).

Używany przez źródło dlt (entsoe_source.py). Zawiera:
  - TokenManager       (auth Keycloak, password grant + refresh na 401)
  - RateLimiter        (limit 100 req/min, thread-safe)
  - fms_post           (POST z retry/backoff/429)
  - fetch_export_log   (pobiera i parsuje Export_log_r3.csv)
  - filename_to_folder / normalize_filename
  - download_file_content (pobiera zawartość pliku jako tekst)
"""

import csv
import io
import re
import threading
import time

import requests

TOKEN_URL = "https://keycloak.tp.entsoe.eu/realms/tp/protocol/openid-connect/token"
FMS_URL = "https://fms.tp.entsoe.eu/"
CLIENT_ID = "tp-fms-public"
TOP_LEVEL = "TP_export"

LOG_FOLDER = "/TP_export/"
LOG_FILENAME = "Export_log_r3.csv"

RATE_LIMIT_PER_MIN = 100
REQUEST_TIMEOUT = 180


class TokenManager:
    """Trzyma token; loguje się ponownie gdy wygaśnie lub dostaniemy 401."""

    def __init__(self, username, password):
        self._username = username
        self._password = password
        self._lock = threading.Lock()
        self._token = None

    def _login(self):
        if not self._username or not self._password:
            raise RuntimeError("Brak poświadczeń (username/password).")
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


class RateLimiter:
    """Thread-safe limiter trzymający się poniżej max_per_min żądań/minutę."""

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
    """POST do FMS z odświeżaniem tokena (401), backoffem na 429 i retry sieci."""
    url = FMS_URL.rstrip("/") + "/" + endpoint
    for attempt in range(retries):
        token = token_manager.get()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        _rate_limiter.wait()
        try:
            resp = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
        except requests.exceptions.RequestException:
            time.sleep(5 * (attempt + 1))
            continue
        if resp.status_code == 401:
            token_manager.refresh()
            continue
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else 600.0
            time.sleep(wait)
            continue
        if resp.status_code >= 400:
            raise RuntimeError(f"{endpoint} HTTP {resp.status_code}: {resp.text[:500]}")
        return resp
    raise RuntimeError(f"{endpoint} nieudane po {retries} próbach.")


def fetch_export_log(token_manager):
    """Pobiera Export_log_r3.csv i zwraca listę {file_name, max_update_time}."""
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


_DATE_PREFIX = re.compile(r"^\d{4}_\d{2}(?:_\d{2})?_")


def filename_to_folder(filename):
    name = filename[:-4] if filename.lower().endswith(".csv") else filename
    return _DATE_PREFIX.sub("", name)


def normalize_filename(filename):
    return filename if filename.lower().endswith(".csv") else filename + ".csv"


def download_file_content(token_manager, folder, filename):
    """Pobiera zawartość pliku (folder + filename) i zwraca surowy tekst CSV."""
    resp = fms_post(token_manager, "downloadFileContent", {
        "folder": f"/{TOP_LEVEL}/{folder}/",
        "filename": filename,
        "topLevelFolder": TOP_LEVEL,
        "downloadAsZip": False,
    })
    return resp.text
