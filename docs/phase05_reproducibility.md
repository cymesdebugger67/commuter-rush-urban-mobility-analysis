# The Commuter Rush — analytical reproducibility

**Author:** Cyril James Lunzaga

## Execution environment

Use a current Python version compatible with the repository requirements (verified locally with Python 3.14.10, pandas 2.3.3 and Matplotlib 3.11.2). Run PowerShell from the project root. A `.venv` created inside the repository and `pip install -r requirements.txt` are recommended. An optional notebook kernel can be installed with `python -m pip install ipykernel`; do not change global Python configurations. The project source uses NumPy indirectly through pandas and statistical modules.

## Source and data limitations

Source: New York State Open Data, Metropolitan Transportation Authority, [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s), Socrata dataset ID `wujg-7c2s`. Restrict to local timestamps `2024-10-01 00:00:00` inclusive and `2024-11-01 00:00:00` exclusive and `transit_mode='subway'`. Fare-category estimates are summed by station complex and hour, with individual category rows and daily MTA server-side source totals reconciled. `transfers` is a component already counted within ridership, not additional entries.

The downloader writes 31 daily JSON snapshots under `data/raw` and a processed CSV under `data/processed`; both directories are ignored by Git. The raw official dataset and processed CSV are not distributed with the public repository. API availability, upstream revisions and rate limits may affect future retrieval. Data retrieval must be followed by independent monthly checks and file-hash verification; do not assume reacquired data necessarily matches a frozen 2026 download.

## Reproduction pipeline

From the repository root, with the project environment active:

```powershell
python -m unittest discover -s tests -p "test_*.py" -q
python -m commuter_rush.source_probe
python -m commuter_rush.monthly_acquisition --mode canary
python -m commuter_rush.monthly_acquisition --mode month
python -m commuter_rush.temporal_analysis
python -m commuter_rush.temporal_visuals
python -m commuter_rush.statistical_evidence
python -m commuter_rush.station_behaviors
python -m commuter_rush.evidence_figures
python -m commuter_rush.release_sensitivity
python -m commuter_rush.notebook_check
python -m commuter_rush.release_audit
```

The canary uses October 9. Each day is cached with auditable SHA-256, verified source totals and source metadata conflicts. The monthly extraction must pass all 31 daily checks before downstream analysis. `python -m commuter_rush.verify_evidence` can be used when its review ZIP does not already exist; the verifier deliberately rejects overwriting previous review archives. After rerunning figures, rerun relevant artifact verification and review images visually before publication.

The notebook `notebooks/commuter_rush_case_study.ipynb` can be opened in VS Code, using the project `.venv` as its kernel. It provides an independently executable, compact walk-through of the cleaned source, day-type normalization, peak-hour contrast, and station orientation. Notebook outputs are intentionally not embedded. The optional terminal checker runs the six trusted code cells sequentially, verifies their values against the saved October manifest, and records an ignored JSON audit. This is a Python-code-cell execution check, not a claim of interactive Jupyter kernel execution. After installing `ipykernel`, a separate interactive VS Code notebook run is optional.

## Quality domains

- Completeness: 31 days, 744 observed clock hours, distinct station coverage by hour. Missing station-hour != zero entry count.
- Accuracy and validity: parse timestamps, finite/nonnegative entries, transfers not exceeding entries, plausible coordinate bounds.
- Consistency: station-complex ID and local-hour key. Source coordinate variations retained and summarized; a deterministic representative geometry is descriptive rather than authoritative.
- Integrity: unique station-hour keys, source fare-record count, day-level reconciliation, raw snapshots and processed CSV SHA-256.
- Statistical interpretation: day-level (not station-hour pseudo-independent) resampling; separate weekday/weekend samples; fixed rush windows and a predeclared station orientation threshold. Bootstrap intervals summarize within-month date-level variability, not population forecasts or causes.

## Publication and authorship

Public creator and author: **Cyril James Lunzaga**. The official data remains owned by the MTA, and source attribution should be displayed in the README and reports. Confirm current publisher conditions and attribution requirements before distributing data extracts. Avoid including raw downloads, local credentials, `.venv`, generated review ZIPs, or sensitive machine-specific paths in Git history.

## Final release quality gate

Run `python -W error::DeprecationWarning -m unittest discover -s tests -p "test_*.py" -q` before publication. NumPy is declared directly in requirements because the statistical code imports it. The release audit verifies the correct README, source-linked 18 tables (including the two-row sensitivity comparison), nine figures, three reports, source and notebook fingerprints, and Git candidate-file exclusions without publishing or overwriting historical review archives. Review the complete staged Git diff before committing, and separately review the final GitHub page after publication.
