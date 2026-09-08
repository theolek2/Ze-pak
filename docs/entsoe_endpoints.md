# Backlog ENTSO-E (Transparency Platform File Library)

API: `https://fms.tp.entsoe.eu/` (PROD) — POST + Keycloak auth, dane jako tab-separowane CSV.
Wykrywanie zmian: `Export_log_r3.csv` (kolumny: file_name, year, month, max_update_time(UTC), export_time(UTC)).
Dataset w bazie: `raw` (tabele: `energy_prices`, ...).

Legenda statusu:
- ✅ zrobione
- ⬜ do zrobienia

## PODSUMOWANIE

- **Zrobione:** 1 instrument — `EnergyPrices_12.1.D_r3.1` (pipeline dlt + dbt: `stg_energy_prices`, `dim_area`, `fct_energy_prices`).
- **Do zrobienia:** pozostałe instrumenty. Najbliższe (były w starym scraperze): `GenerationForecastsForWindAndSolar_14.1.D`, `AggregatedGenerationPerType_16.1.B_C`, `ImbalancePrices_17.1.G_r3.1`.

## Jak dodać kolejny instrument (wzorzec)

1. `sources/entsoe/entsoe_source.py` — dodać kolumnę do mapowania pól (każdy instrument ma inny nagłówek CSV).
2. Uruchomić `run_pipeline.py --entsoe-only --seed` (baseline, bez pobierania).
3. dbt: `staging/entsoe/stg_<instrument>.sql` + ewentualnie `marts/entsoe/fct_<instrument>.sql`.

> Uwaga: `entsoe_source.py` jest obecnie zahardkodowane na `EnergyPrices_12.1.D_r3.1` (TARGET). Żeby obsłużyć wiele instrumentów, trzeba przerobić na fabrykę (jak w `pse_source.py` — słownik ENCJI → resource).

## Instrumenty (katalog z File Library Guide)

### Market (rynek)

| Instrument | Status |
|---|---|
| EnergyPrices_12.1.D_r3.1 | ✅ |
| AuctionRevenue_12.1.A_r3 | ⬜ |
| FlowBasedAllocationsCongestionIncome_12.1.E_r3 | ⬜ |
| FlowBasedCapacityAllocation_11.1.B_r3 | ⬜ |
| ImplicitAllocationsCongestionIncome_12.1.E_r3 | ⬜ |
| ImplicitAllocationsNetPositions_12.1.E_r3.1 | ⬜ |
| OfferedTransferCapacitiesContinuous_11.1_r3.1 | ⬜ |
| OfferedTransferCapacitiesExplicit_11.1_r3.1 | ⬜ |
| OfferedTransferCapacitiesImplicit_11.1_r3.1 | ⬜ |
| TotalCapacityAlreadyAllocated_12.1.C_r3 | ⬜ |
| TotalCapacityNominated_12.1.B_r3 | ⬜ |
| TransferCapacitiesAllocatedWithThirdCountries_12.1.H_r3 | ⬜ |
| UseOfTransferCapacity_12.1.A_r3 | ⬜ |

### Load (obciążenie)

| Instrument | Status |
|---|---|
| ActualTotalLoad_6.1.A_r3 | ⬜ |
| DayAheadTotalLoadForecast_6.1.B_r3 | ⬜ |
| TotalLoadForecast_6.1.C_D_E_r3 | ⬜ |
| YearAheadForecastMargin_8.1_r3 | ⬜ |

### Generation (generacja)

| Instrument | Status |
|---|---|
| AggregatedGenerationPerType_16.1.B_C_r3 | ⬜ (był w starym scraperze) |
| GenerationForecastsForWindAndSolar_14.1.D_r3 | ⬜ (był w starym scraperze) |
| ActualGenerationOutputPerGenerationUnit_16.1.A_r3 | ⬜ |
| AggregatedFillingRateOfWaterReservoirs_16.1.D_r3 | ⬜ |
| DayAheadAggregatedGeneration_14.1.C_r3 | ⬜ |
| InstalledGenerationCapacityAggregated_14.1.A_r3 | ⬜ |
| InstalledGenerationCapacityPerProductionUnit_14.1.B_r3.1 | ⬜ |
| ProductionAndGenerationUnits_r3.1 | ⬜ |

### Transmission (przesył)

| Instrument | Status |
|---|---|
| PhysicalFlows_12.1.G_r3 | ⬜ |
| CommercialSchedules_12.1.F_r3.1 | ⬜ |
| CommercialSchedulesNetPositions_12.1.F_r3.1 | ⬜ |
| CostsOfCongestionManagement_13.1.C_r3 | ⬜ |
| Countertrading_13.1.B_r3.2 | ⬜ |
| CrossBorderCapacityForDcLinksIntradayTransferLimits_11.3_r3 | ⬜ |
| ExpansionAndDismantlingProjects_9.1_r3 | ⬜ |
| ForecastedTransferCapacities_11.1_r3.1 | ⬜ |
| RedispatchingCrossBorder_13.1.A_r3.2 | ⬜ |
| RedispatchingInternal_13.1.A_r3.2 | ⬜ |
| TransmissionAssets_r3.1 | ⬜ |

### Outages (awarie)

| Instrument | Status |
|---|---|
| UnavailabilityInTheTransmissionGrid_10.1.A_B_r3.1 | ⬜ |
| UnavailabilityOfConsumptionUnits_7.1.A_B_r3 | ⬜ |
| UnavailabilityOfOffshoreGrid_10.1.C_r3.1 | ⬜ |
| UnavailabilityOfProductionAndGenerationUnits_15.1.A_B_C_D_r3.1 | ⬜ |

### Balancing (bilansowanie)

| Instrument | Status |
|---|---|
| ImbalancePrices_17.1.G_r3.1 | ⬜ (był w starym scraperze) |
| CurrentBalancingState_12.3.A_r3 | ⬜ |
| AggregatedBalancingEnergyBids_12.3.E_r3.1 | ⬜ |
| AmountAndPricesPaidOfBalancingReservesUnderContract_17.1.B_C_r3.1 | ⬜ |
| BalancingEnergyBids_12.3.B_C_r3.1 | ⬜ |
| CrossZonalBalancingCapacity_12.3.H_12.3.I_r3.1 | ⬜ |
| FinancialExpensesAndIncomeForBalancing_17.1.I_r3 | ⬜ |
| ImbalanceNetting_186.2_r3 | ⬜ |
| NettedAndExchangedVolumes_IFs_IN3.10_mFRR3.17_r3.1 | ⬜ |
| PricesOfActivatedBalancingEnergy_17.1.F_r3.1 | ⬜ |
| ProcuredBalancingCapacity_12.3.F_r3.1 | ⬜ |
| TotalImbalanceVolumes_17.1.H_r3.1 | ⬜ |

## Uwagi

- ENTSO-E migruje instrumenty na `_r3.1`/`_r3.2` — zawsze preferuj najnowszy sufiks (sprawdź w `Export_log_r3.csv`).
- Oferty bilansowania ENTSO-E (w przeciwieństwie do PSE) **nie** mają odpowiednika "kto zaoferował" — to też dane zagregowane. Poziomy per-uczestnik są w innym, autoryzowanym dostępie.
- Priorytetyzacja: najpierw `AggregatedGenerationPerType`, `GenerationForecastsForWindAndSolar`, `ImbalancePrices` (były w starym scraperze), potem Load/Market.
