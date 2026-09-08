# Backlog endpointów PSE (Raporty OSP / Market Data)

API: `https://api.raporty.pse.pl/api/` — publiczne (bez auth), REST + OData.
Specyfikacja: `https://api.raporty.pse.pl/api/openapi`
Incremental: `$filter=publication_ts_utc gt '<YYYY-MM-DD HH:MM:SS>'` (kolumny `_utc` są w UTC).

Legenda statusu:
- ✅ zrobione (Tor A)
- ⬜ do zrobienia
- ⚠️ nieaktualne / ciężkie (timeout) — zweryfikować osobno

## PODSUMOWANIE

- **Zrobione (Tor A, świeże encje):** `use_sprz_rbb/rbn`, `mbp_tp`, `cmbp_tp`, `zmb`, `kmb_kro_rozl`, `cor`, `csdac_pln`, `price_fcst` — pipeline dlt (`raw_pse`) + dbt (`stg_pse_*`, `fct_pse_procurement`, `fct_pse_balancing_prices`).
- **Do zrobienia:** pozostałe ceny (`codn`, `cor-q-1`, `cordmax`, `price-cost`, `rce-pln`, `rcco2`), koszty/energia (Etap 3), moce (Etap 4), Tor B (jednostki z ID).
- **Do weryfikacji (⚠️):** oferty `poeb-*`, `pomb-rbn`, `popmb-rmb`, `oeb-bpkdbo` — nieaktualne (~2024) lub timeout; sprawdzić czy PSE ma nowsze odpowiedniki po reformie rynku.

## Etap 1 — Oferty + zakup (Tor A)

| Endpoint | Co to | Status |
|---|---|---|
| poeb-rbb / poeb-rbn | Oferty energii bilansującej (RBB/RBN) | ⚠️ nieaktualne (~2024) |
| pomb-rbn | Oferty mocy wg produktu | ⚠️ timeout |
| popmb-rmb | Oferty portfolio (POM/COM/COMRR) | ⚠️ nieaktualne (~2024) |
| oeb-bpkdbo | Oferty wg bramek cenowych (krzywa) | ⚠️ timeout |
| use-sprz-rbb / use-sprz-rbn | Dostawy USE (wolumen) | ✅ |
| mbp-tp | Kupione moce (tryb podstawowy) | ✅ |
| cmbp-tp | Ceny kupionych mocy | ✅ |
| kmb-kro-rozl | Koszty (KMB + KRO) | ✅ |

## Etap 2 — Ceny bilansowania

| Endpoint | Co to | Status |
|---|---|---|
| codn | Cena odchylenia (miesięczna) | ⬜ |
| cor | COR (cena rozliczeniowa odchylenia) | ✅ |
| cor-q-1 | COR* bez ostatniej doby kwartału | ⬜ |
| cordmax | Górny limit CORDMax | ⬜ |
| csdac-pln | Cena SDAC | ✅ |
| price-cost | Cena/koszt bilansowania | ⬜ |
| price-fcst | Prognoza ceny | ✅ |
| rce-pln | Rozliczeniowa cena energii | ⬜ |
| rcco2 | Cena CO2 | ⬜ |

## Etap 3 — Koszty + energia

| Endpoint | Co to | Status |
|---|---|---|
| krb-rozl | Koszt rynku bilansującego | ⬜ |
| crb-rozl | Cena rynku bilansującego | ⬜ |
| eb-rozl | Energia bilansująca | ⬜ |
| en-rozl | Energia niebilansowania (saldo) | ⬜ |
| ro-rozl / ro-prog | Rezerwa operacyjna | ⬜ |
| zeb-rozl | ZEBPP | ⬜ |

## Etap 4 — Moce + parametry

| Endpoint | Co to | Status |
|---|---|---|
| zmb | Zapotrzebowanie na moce bilansujące | ✅ |
| mbu-tu / cmbu-tu | Moce / ceny w trybie użycia | ⬜ |
| wmb | Wielkości mocy bilansujących | ⬜ |
| wsp-wrm | Parametry wymaganej rezerwy | ⬜ |
| afrr-status | Status aFRR | ⬜ |
| lolp | Loss of Load Probability | ⬜ |
| sk | Saldo kosztów | ⬜ |

## Tor B (jednostki z ID) — przyszłość

| Endpoint | Co to | ID |
|---|---|---|
| gen-jw | Generacja per jednostka | resource_code, power_plant |
| ogr-r / ogr-b / ogr-d1 / ogr-d2 / ogr-d39 / ogr-m / ogr-oper | Ograniczenia per jednostka | resource_name, resource_code |
| ogr-rmb | Ograniczenia RMB per jednostka | id, unit_name, direction |
| unav-pk5l | Awarie per jednostka | unit_code, power_plant |
| pdwkseub | Dostępna moc per jednostka | power_plant, resource_code |

Wymaga: wspólny wymiar `dim_unit` (resource_code + power_plant).
