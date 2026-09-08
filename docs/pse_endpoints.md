# PSE — Raporty OSP / Market Data (backlog)

API: `https://api.raporty.pse.pl/api/` — publiczne (bez auth), REST + OData.
Specyfikacja: `https://api.raporty.pse.pl/api/openapi`

**Strategie incremental (filtr per encja):**
- `publication_ts_utc` → `$filter=publication_ts_utc gt '<czas>'` — szybkie encje (domyślna).
- `business_date` → `$filter=business_date eq '<doba>'` (pętla po dniach) — ciężkie encje ofertowe, gdzie filtr po publication_ts_utc timeoutuje.

**Jak dodać encję:** dopisz jedną linię w `sources/pse/pse_source.py` → `ENTITIES`, np.:
```python
"poeb_rbb": {"endpoint": "poeb-rbb", "incremental": "business_date"},
```
potem `stg_pse_<encja>.sql` + ewentualny mart.

---

## Aktywne (w pipeline)

| Encja | Co to | Strategia |
|---|---|---|
| `zmb` | Zapotrzebowanie na moce bilansujące nabywane w RMB (FCR/FRR/aFRR/RR ↑↓, MW) — publikowane raz dziennie rano | `publication_ts_utc` |
| `cor` | COR — cena rozliczeniowa odchylenia (15-min, `cor_fcst` prognoza w czasie rzeczywistym + `cor_cost` po rozliczeniu) | `publication_ts_utc` |

---

## TODO — Oferty (bety, anonimowe)

Dane = indywidualne oferty (krzywa ofertowa / merit order), ale **bez nazwy uczestnika** (pola: cena + wolumen). Wiele wierszy na kwadrans → dużo danych.

| Encja | Co to | Strategia |
|---|---|---|
| `poeb-rbb` | Oferty energii bilansującej (RBB): `ofp` cena, `ofcg`/`ofcd` skumulowany wolumen ↑/↓ | `business_date` |
| `poeb-rbn` | Oferty energii bilansującej (RBN): jw. | `business_date` |
| `pomb-rbn` | Oferty mocy wg produktu (`reserve_type` FCRᴳ/FCRᴰ) + przedział cen `pofmin/pofmax` + wolumen `ofc` | `business_date` |
| `popmb-rmb` | Oferty portfolio na moce (`com` cena, `pom`, `comrr`, wg `reserve_type`) | `publication_ts_utc` |
| `oeb-bpkdbo` | Bety posortowane (`sort`, `activ_direction` ↑/↓, `ofp`, `ofc`, `cdo`) | `business_date` |

## TODO — Zakup mocy bilansującej (co kupiono / po ile)

| Encja | Co to | Strategia |
|---|---|---|
| `mbp-tp` | Kupione moce w trybie podstawowym (ONMBP, FCR/aFRR/mFRR/RR ↑↓, MW) | `publication_ts_utc` |
| `cmbp-tp` | Ceny kupionych mocy (per produkt, PLN/MW) | `publication_ts_utc` |
| `mbu-tu` | Moce w trybie użycia | `publication_ts_utc` |
| `cmbu-tu` | Ceny mocy w trybie użycia | `publication_ts_utc` |
| `wmb` | Wielkości mocy bilansujących | `publication_ts_utc` |

## TODO — Ceny bilansowania

| Encja | Co to | Strategia |
|---|---|---|
| `codn` | Cena odchylenia (miesięczna) | `publication_ts_utc` |
| `cor-q-1` | COR* bez ostatniej doby kwartału | `publication_ts_utc` |
| `cordmax` | Górny limit CORDMax | `publication_ts_utc` |
| `csdac-pln` | Cena SDAC (rynek dnia następnego, PLN) | `publication_ts_utc` |
| `price-cost` | Cena/koszt bilansowania | `publication_ts_utc` |
| `price-fcst` | Prognoza ceny (cen/cor/ckoeb/ceb) | `publication_ts_utc` |
| `rce-pln` | Rozliczeniowa cena energii (15-min) | `publication_ts_utc` |
| `rcco2` | Cena CO2 | `publication_ts_utc` |

## TODO — Koszty + energia bilansująca

| Encja | Co to | Strategia |
|---|---|---|
| `kmb-kro-rozl` | Koszt mocy bilansujących KMB + rezerwy operacyjnej KRO | `publication_ts_utc` |
| `krb-rozl` | Koszt rynku bilansującego | `publication_ts_utc` |
| `crb-rozl` | Cena rynku bilansującego | `publication_ts_utc` |
| `eb-rozl` | Energia bilansująca (rozliczeniowa) | `publication_ts_utc` |
| `en-rozl` | Energia niebilansowania (saldo) | `publication_ts_utc` |
| `ro-rozl` / `ro-prog` | Rezerwa operacyjna (aktualna/prognoza) | `publication_ts_utc` |
| `zeb-rozl` | ZEBPP — energia bilansująca poza platformą RR | `publication_ts_utc` |
| `use-sprz-rbb` / `use-sprz-rbn` | Dostawy USE (wolumen sprzedaży energii bilansującej) | `publication_ts_utc` |

## TODO — Parametry / inne

| Encja | Co to | Strategia |
|---|---|---|
| `wsp-wrm` | Parametry wymaganej wielkości rezerwy mocy (OJNZ, aFW, aPV, aWS) | `publication_ts_utc` |
| `afrr-status` | Status aFRR (event_time, reason) | `publication_ts_utc` |
| `lolp` | Loss of Load Probability | `publication_ts_utc` |
| `sk` | Stan zakontraktowania KSE | `publication_ts_utc` |

## TODO — Tor B (jednostki z ID) — wymaga `dim_unit`

| Encja | Co to | ID |
|---|---|---|
| `gen-jw` | Generacja per jednostka (MW, tryb pracy) | `resource_code`, `power_plant` |
| `ogr-r` / `ogr-b` / `ogr-d1` / `ogr-d2` / `ogr-d39` / `ogr-m` / `ogr-oper` | Ograniczenia per jednostka | `resource_name`, `resource_code` |
| `ogr-rmb` | Ograniczenia RMB per jednostka (kierunek ↑↓, SMINP/SMAXP) | `id`, `unit_name` |
| `unav-pk5l` | Awarie per jednostka | `unit_code`, `power_plant` |
| `pdwkseub` | Dostępna moc per jednostka | `power_plant`, `resource_code` |

> Tor B to odpowiedź na "kto (jednostka) kiedy ile" — wymaga wspólnego wymiaru `dim_unit` (resource_code + power_plant), analogicznie do `dim_area` w ENTSO-E.
