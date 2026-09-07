# ENTSO-E Energy Warehouse

Mini-hurtownia danych o energetyce (na start: ceny energii ENTSO-E), zbudowana wg wzorca **ELT**:

```
ENTSO-E API → dlt (pobiera) → DuckDB (baza) → dbt (modeluje) → Streamlit (podgląd)
```

- **dlt** pobiera z API tylko pliki, które zmieniły się od ostatniego uruchomienia (wg logu `Export_log_r3.csv`) i ładuje je do DuckDB (warstwa `raw`).
- **dbt** typuje, deduplikuje i buduje model gwiazdy (`dim_area` + `fct_energy_prices`) w schemacie `analytics`.
- **Streamlit** pokazuje zawartość bazy i wykres cen.

## Struktura plików

| Plik / folder | Co robi |
|---|---|
| `pipeline/entsoe_client.py` | Wspólny klient API ENTSO-E: auth (Keycloak), rate-limit, log, pobieranie plików |
| `pipeline/entsoe_source.py` | Źródło dlt: parsuje `EnergyPrices_12.1.D` i yield'uje wiersze |
| `pipeline/run_pipeline.py` | Entry point pipeline dlt → `energy.duckdb` (`--seed` ustawia baseline) |
| `pipeline/run_pipeline.bat` | Wrapper do Windows Task Scheduler (co godzinę) |
| `app.py` | Aplikacja Streamlit: podgląd tabel + wykres cen |
| `dbt/` | Projekt dbt: `stg_energy_prices`, `dim_area`, `fct_energy_prices` |
| `energy.duckdb` | Baza (plik, build artifact — gitignored) |
| `requirements.txt` | Zależności Pythona |
| `stary_scraper/` | **Legacy** scraper (MVP, pobierał CSV do plików). Nieużywany — można usunąć |

## Uruchomienie

```powershell
# 1. Środowisko
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt

# 2. Poświadczenia ENTSO-E → .dlt\secrets.toml
#    entsoe_username = "..."
#    entsoe_password = "..."

# 3. Pipeline (baseline, potem co godzinę przez Task Scheduler)
.venv\Scripts\python.exe pipeline\run_pipeline.py --seed
.venv\Scripts\python.exe pipeline\run_pipeline.py

# 4. Model dbt
cd dbt
..\.venv\Scripts\dbt.exe run --profiles-dir .

# 5. Podgląd
cd ..
.venv\Scripts\python.exe -m streamlit run app.py
```

## Model danych (grain)

`fct_energy_prices` — jedna cena na `(datetime, resolution_code, area_map_code, contract_type)`.
`dim_area` — wspólny wymiar obszaru (`area_map_code` = klucz naturalny), do którego dołączą kolejne źródła.

## model użyty do kogowania: deepseek V4 Pro - modem - opencode