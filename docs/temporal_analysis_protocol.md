# October 2024 — descriptive temporal analysis protocol

- **Author:** Cyril James Lunzaga
- **Source:** MTA Subway Hourly Ridership: 2020–2024, dataset `wujg-7c2s`
- **Primary grain:** Unique station-complex ID × New York local hour

## Frozen descriptive questions

1. How does estimated station-entry demand vary by day and by local clock hour?
2. How does mean hourly demand differ descriptively between weekdays and weekends after normalizing by the number of days?
3. What proportions of weekday entries fall within 07:00–09:59 and 16:00–18:59, and how do those shares vary by borough?
4. Which complexes have the highest estimated entry totals, and how concentrated are system entries across complexes?
5. What is the observed station reporting coverage, particularly within peak-hour comparisons?

## Definitions and analysis boundaries

- **Weekdays:** Monday–Friday by source-local calendar time. October 2024 contains 23 weekdays and 8 weekend days.
- **Morning window:** 07:00, 08:00, 09:00 hour-beginning records; **evening window:** 16:00, 17:00, 18:00. Both windows contain three hours per weekday.
- **Day-type hourly mean:** Total estimated entries from all observed stations during a day/hour, averaged over the number of weekdays or weekend days, not over the number of station-hour observations. This avoids confusing 23 weekdays with 8 weekend days.
- **Borough peak share:** Entries in the three-hour window divided by all observed entries in the same borough across all weekday hours. The denominator is not systemwide borough population.
- **Station concentration:** Station shares of the month's observed entries, the contribution of the ten highest-volume complexes, and a descriptive Gini coefficient over observed station totals. No representativeness claim is attached to the coefficient.
- **Primary peak ranking:** Only station complexes with at least 90% of expected observed hours in both morning and evening windows. Excluded stations remain in the network totals; exclusion does not imply zero demand.
- **Missing:** An absent station-hour stays absent. Observed zeros, if any, retain their source value. All 744 clock hours are observed somewhere but per-complex reporting is variable.
- **Map coordinates:** Representative source coordinates are available but not definitive geocodes. The first descriptive checkpoint does not generate a spatial risk or congestion map.

## Data-contract gate

Before computing research tables, validate the acquisition manifest (`month_acquisition_passed`, 31 days, source-control reconciliations, frozen coverage, metadata conflict audit), the processed CSV's exact SHA-256 and byte count, unique station-hour keys, expected column schema, count and station inventory, source-local timestamps, numeric validity, transfer subset, and total sums. No result may proceed on a mismatched fingerprint.

All published tables and figures must originate from these validated local inputs. The original source file and intermediary diagnostic snapshots remain excluded from GitHub.

## Curated outputs

`commuter_rush.temporal_analysis` produces ten descriptive CSV tables under `portfolio/tables/`, a generated research note under `portfolio/reports/`, and an ignored summary/index under `outputs/temporal_analysis/` with hashes.

`commuter_rush.temporal_visuals` validates table hashes before creating six PNGs under `portfolio/figures/`: daily entries, weekday/weekend mean hourly entries, weekday-by-hour heatmap, borough peak shares, highest-volume complexes, and station concentration. The images are provisional until inspected for readability, station labeling, scale, and actual numerical consistency.

Neither phase estimates capacity utilization, train crowding, trip time, passenger journeys, station throughput capacity, or causal effects. Statistical uncertainty and clustering are deferred until the genuine results and coverage patterns are reviewed.

## Reproduction

```powershell
$py = '.\.venv\Scripts\python.exe'
& $py -m pip install -r requirements.txt
& $py -m unittest discover -s tests -p 'test_*.py' -q
& $py -m commuter_rush.temporal_analysis
& $py -m commuter_rush.temporal_visuals
```

Do not interpret numbers produced by the synthetic test fixtures as observed transport findings.
