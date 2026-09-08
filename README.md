# Energy Warehouse (ENTSO-E + PSE)

Mini-hurtownia danych o energetyce (ceny energii ENTSO-E + rynek bilansowania PSE), zbudowana wg wzorca **ELT**:

```
ENTSO-E API ─┐
             ├─> dlt (pobiera) ─> DuckDB (baza) ─> dbt (modeluje) ─> Streamlit (podgląd)
PSE API     ─┘
```

- **dlt** pobiera z API tylko dane, które zmieniły się od ostatniego uruchomienia i ładuje do DuckDB (dataset `raw` dla ENTSO-E, `raw_pse` dla PSE).
- **dbt** typuje, deduplikuje i buduje model gwiazdy w schemacie `analytics`.
- **Streamlit** pokazuje zawartość bazy i wykresy.

## Źródła danych

| Źródło | Opis | Auth | Dataset |
|---|---|---|---|
| ENTSO-E File Library | Ceny energii (EnergyPrices 12.1.D) | Keycloak (login/hasło) | `raw` |
| PSE Raporty OSP | Rynek bilansowania (zakup, dostawy, ceny) | publiczne (brak) | `raw_pse` |

## Struktura plików

| Plik / folder | Co robi |
|---|---|
| `sources/entsoe/` | Źródło ENTSO-E: `entsoe_client.py` (auth/rate-limit/log), `entsoe_source.py` (dlt) |
| `sources/pse/` | Źródło PSE: `pse_client.py` (OData), `pse_source.py` (dlt, incremental) |
| `pipeline/run_pipeline.py` | Orchestrator: odpala oba źródła (`--seed`, `--backfill-days N`, `--pse-only`) |
| `pipeline/run_pipeline.bat` | Wrapper Task Scheduler: dlt + dbt run |
| `dbt/models/staging/entsoe/`, `staging/pse/` | Staging (dedupe + typowanie) |
| `dbt/models/marts/entsoe/`, `marts/pse/` | Martsy: `dim_area`, `fct_energy_prices`, `fct_pse_procurement`, `fct_pse_balancing_prices` |
| `app.py` | Aplikacja Streamlit (read-only, UTC) |
| `docs/pse_endpoints.md` | Backlog endpointów PSE (4 etapy + Tor B) |
| `energy.duckdb` | Baza (plik, gitignored) |
| `.dlt/secrets.toml` | Poświadczenia ENTSO-E (gitignored) |
| `stary_scraper/` | **Legacy** scraper CSV (nieużywany) |

## Uruchomienie

```powershell
# 1. Środowisko
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Poświadczenia ENTSO-E → .dlt\secrets.toml
#    entsoe_username = "..."
#    entsoe_password = "..."   (PSE nie wymaga poświadczeń)

# 3. Pipeline (baseline, potem co godzinę przez Task Scheduler)
.venv\Scripts\python.exe pipeline\run_pipeline.py --seed
.venv\Scripts\python.exe pipeline\run_pipeline.py --backfill-days 2   # PSE: wstecz N dni (test)

# 4. Modele dbt
cd dbt
..\.venv\Scripts\dbt.exe run --profiles-dir .

# 5. Podgląd
cd ..
.venv\Scripts\python.exe -m streamlit run app.py
```

## Model danych

- `fct_energy_prices` (entsoe) — grain: `(datetime, resolution_code, area_map_code, contract_type)`.
- `dim_area` — wspólny wymiar obszaru (`area_map_code` = klucz naturalny).
- `fct_pse_procurement` (pse) — kupione moce bilansujące: `(dtime_utc, product, quantity_mw, price_pln_per_mw)`.
- `fct_pse_balancing_prices` (pse) — ceny: `(dtime_utc, price_type, price)`.

Wszystkie znaczniki czasu są w **UTC** (kolumny `_utc`, DuckDB `TimeZone='UTC'`).
