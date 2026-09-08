#!/usr/bin/env python3
r"""
Klient API PSE (Raporty OSP / Market Data) — bez autoryzacji, REST + OData.

Endpoint bazowy: https://api.raporty.pse.pl/api/
Styl OData: $select, $filter, $orderby, $first, $after (cursor w nextLink).
Odpowiedź: JSON {"value": [...], "nextLink": "..."}.
"""

import time

import requests

BASE_URL = "https://api.raporty.pse.pl/api/"

REQUEST_TIMEOUT = 60
# grzecznościowy limit (PSE nie narzuca, ale nie chcemy przeciążać)
REQUEST_DELAY = 0.2


def fetch(entity, filter=None, first=None):
    """GET <entity> z parametrami OData; yield'uje wiersze, podąża za nextLink."""
    url = BASE_URL + entity
    params = {}
    if filter:
        params["$filter"] = filter
    if first:
        params["$first"] = first

    while url:
        resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        for row in data.get("value", []):
            yield row

        url = data.get("nextLink")
        params = {}  # nextLink ma już pełne parametry
        if url:
            time.sleep(REQUEST_DELAY)


def utc_now_str():
    """Aktualny czas UTC w formacie pasującym do publication_ts_utc."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
