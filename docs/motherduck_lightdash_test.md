# MotherDuck + Lightdash — tymczasowy test, bez trwałej integracji

Cel: jednorazowo sprawdzić wszystkie bieżące tabele analityczne w Lightdash.
Nie modyfikujemy w tym celu kodu pipeline, profili dbt ani harmonogramu.

## Zakres testu

Katalog `analytics` w lokalnym `energy.duckdb`, stan z kontrolnego odczytu:

| Obiekt | Typ | Liczba wierszy |
|---|---:|---:|
| `analytics.dim_area` | tabela | 49 |
| `analytics.fct_energy_prices` | tabela | 296119 |
| `analytics.fct_pse_zmb` | tabela | 576 |
| `analytics.fct_pse_cor` | tabela | 421 |
| `analytics.stg_energy_prices` | widok | 296119 |
| `analytics.stg_pse_zmb` | widok | 72 |
| `analytics.stg_pse_cor` | widok | 421 |

Stempel znaczników czasu weryfikacyjnych: 2026-09-09, UTC.

Nie kopiujemy:

- `raw.*`,
- `raw_pse.*`,
- żadnych tabel `_dlt_*`,
- `.dlt/secrets.toml`,
- tokenów i haseł.

## Zasady testu

1. Organizacja MotherDuck w Europie.
2. Jeden użytkownik testowy.
3. Brak karty, dopóki użycie mieści się w limitach Lite.
4. Brak serwisu, harmonogramu i trwałego profilu MotherDuck w repozytorium.
5. Token MotherDuck podawany jest tylko ręcznie w sesji roboczej, nigdy nie trafia do kodu, gita ani dokumentacji.
6. Lightdash łączymy przez istniejące repozytorium, nie przez lokalny deploy CLI.
7. Streamlit usuwamy dopiero po zielonym teście Lightdash.

## Jednorazowa procedura testowa

> Nie uruchamiać, dopóki pipeline, dbt i zamknięcie procesów trzymających bazę nie zostaną potwierdzone.

1. Zamknąć wszystkie procesy trzymające `energy.duckdb`:
   - DuckDB CLI,
   - Streamlit,
   - ręczne sesje Pythona z otwartą bazą.
2. Utworzyć w MotherDuck organizację europejską i jednorazowy token testowy.
3. W lokalnej sesji DuckDB, otwartej bezpośrednio na `energy.duckdb`, wykonać jedynie ręczne polecenia kopiujące. Prawa strona zapytania odnosi się do lokalnej bazy, a w pełni kwalifikowany cel — do bazy MotherDuck, np.:

```sql
INSTALL motherduck;
LOAD motherduck;
SET motherduck_token = '<wklej-ręcznie-token-testowy>';
ATTACH 'md:energy_lightdash_test';
CREATE SCHEMA IF NOT EXISTS energy_lightdash_test.analytics;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.dim_area
AS SELECT * FROM analytics.dim_area;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.fct_energy_prices
AS SELECT * FROM analytics.fct_energy_prices;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.fct_pse_zmb
AS SELECT * FROM analytics.fct_pse_zmb;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.fct_pse_cor
AS SELECT * FROM analytics.fct_pse_cor;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.stg_energy_prices
AS SELECT * FROM analytics.stg_energy_prices;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.stg_pse_zmb
AS SELECT * FROM analytics.stg_pse_zmb;

CREATE OR REPLACE TABLE energy_lightdash_test.analytics.stg_pse_cor
AS SELECT * FROM analytics.stg_pse_cor;
```

4. W Lightdash:
   - utworzyć projekt,
   - wybrać warehouse `DuckDB / MotherDuck`,
   - podać bazę `energy_lightdash_test`,
   - podać schemat `analytics`,
   - podać token wyłącznie w formularzu Lightdash,
   - podłączyć istniejące repozytorium z projektem dbt.
5. Zweryfikować:
   - liczbę tabel,
   - liczbę wierszy na tabelę,
   - maksymalny znacznik czasu UTC,
   - join `fct_energy_prices` z `dim_area`,
   - jedno zapytanie ad hoc SQL.
6. Po teście zdecydować, czy testowa baza MotherDuck zostaje, czy ją usuwamy i wycofujemy token.

## Kontrola kosztów Lite

- Pilnować 10 GB magazynu i 10 godzin obliczeniowych miesięcznie.
- Na test wysyłamy tylko 7 obiektów analitycznych, bez surowych tabel i metadanych pipeline.
- Nie włączać automatycznego godzinowego mirroru na tym etapie.

## Tryb petli 30-min (aktualne, po decyzji)

- Looper: `python pipeline/run_loop.py` (Python loop, nie Task Scheduler).
- Kolejnosc: dlt -> dbt (`--target dev` lokalnie) -> sync append -> Lightdash Cloud (live query, bez triggera).
- Sync doklada tylko nowe wiersze (`sync_motherduck.py`, watermark `max(ts)`, overlap 2 doby na spoznione dane, `_sync_watermark` w MD). `--force` = pelna kopia awaryjna. `dim_area` (slownik, ~50 wierszy) podmieniany w calosci.
- Token: trwaly `MOTHERDUCK_TOKEN` w srodowisku procesu loopa (odstepstwo od zasady "tylko recznie" powyzej).
- Lock: `pipeline/.loop.lock` przeciw nakladaniu obiegow; logi: `logs/loop_YYYY-MM-DD.log`.
- Lekkie testy: `--once --tables fct_pse_cor`, `--dry-run` (offline), `--skip-dlt/--skip-dbt/--skip-sync`.
- Segregacja zrodel: `--source entsoe` (dim_area + 4 fakty ENTSO-E) albo `--source pse` (zmb, cor). Dziala tez w `run_loop.py`.
