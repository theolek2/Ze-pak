#!/usr/bin/env python3
"""Wspólny kontrakt czasu UTC dla źródeł danych.

Wywoływać wyłącznie dla pól, których metadane źródła jawnie deklarują UTC,
np. kolumn ENTSO-E kończących się na ``(UTC)`` oraz kolumn PSE kończących się
na ``_utc``. Funkcja nigdy nie zgaduje strefy dla zwykłych czasów lokalnych.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_TIMESTAMP_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,9})?)?(?:Z|[+-]\d{2}:?\d{2})?$"
)


def _fail(source: str, field: str, value: object, reason: str) -> RuntimeError:
    return RuntimeError(
        f"{source}: invalid UTC timestamp in {field}: {value!r} "
        f"({reason}; oczekiwano ISO 'RRRR-MM-DD GG:MM:SS[.ffffff]'+00:00 "
        "albo naiwnego czasu z pola jawnie zadeklarowanego jako UTC)"
    )


def parse_utc_datetime(
    value: object, *, field: str, source: str, required: bool = True
) -> datetime | None:
    """Sparsuj tekst/czas do świadomego obiektu UTC albo rzuć błąd.

    Naiwny tekst jest akceptowany jedynie dlatego, że wywołujący deklaruje
    przez wybór pola, iż API oznacza je jako UTC. Pusta wartość jest
    dopuszczalna tylko dla pól opcjonalnych.
    """

    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise RuntimeError(
                f"{source}: missing required UTC timestamp in {field}"
            )
        return None

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        if _TIMESTAMP_RE.match(text) is None:
            raise _fail(source, field, value, "malformed")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise _fail(source, field, value, "malformed") from exc
    else:
        raise _fail(source, field, value, "unexpected type")

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    offset = parsed.utcoffset()
    if offset != timedelta(0):
        raise _fail(source, field, value, "non-UTC offset")
    return parsed.astimezone(timezone.utc)


def format_utc_api(value: datetime) -> str:
    """Sformatuj świadomy UTC obiekt do tekstowego API PSE."""
    if value.tzinfo is None:
        raise RuntimeError("UTC datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f")
