# Legacy scraper (MVP) — nieużywany

Ten folder zawiera **stary** scraper ENTSO-E, który pobierał pliki CSV do plików
na dysku. Został zastąpiony przez nowy stack **dlt → DuckDB → dbt** (patrz
`pipeline/` i `dbt/` w katalogu głównym).

## Co tu jest
- `entsoe_scraper.py` — stary scraper (pobiera CSV do `output/`)
- `config.txt` — stare poświadczenia + lista instrumentów
- `run_scraper.bat` — wrapper do Windows Task Scheduler
- `state.json` — stan (lastUpdatedTimestamp per plik)
- `output/` — pobrane pliki CSV (dane testowe)

## Status
- Zadanie w Task Scheduler `ENTSOE_Scraper` jest **wyłączone** (zastąpione przez dlt).
- Kod zachowany jako referencja logiki auth/rate-limit/log — ta logika została
  wydzielona do `pipeline/entsoe_client.py` i jest reuse'owana przez dlt.
