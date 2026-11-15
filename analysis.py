# %% Imports and paths
"""2011–2012 Capital Bikeshare hourly demand. Run: python analysis.py"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "data/raw/hour.csv"
OUT = ROOT / "outputs"


def main():
    if not SOURCE.exists():
        raise SystemExit(f"Dataset missing: {SOURCE}\nDownload hour.csv from the UCI source in README.md.")
    df = pd.read_csv(SOURCE)
    required = {"dteday", "hr", "cnt", "workingday", "weathersit", "season"}
    if required - set(df.columns):
        raise ValueError(f"Missing columns: {sorted(required - set(df.columns))}")
    raw_rows = len(df)
    for c in ["hr", "cnt", "workingday", "weathersit", "season"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["dteday"] = pd.to_datetime(df["dteday"], errors="coerce")
    df = df.dropna(subset=["dteday", "hr", "cnt", "workingday", "weathersit", "season"]).copy()
    df = df.loc[df["hr"].between(0, 23) & df["cnt"].ge(0)].copy()
    if df.empty:
        raise ValueError("No valid hourly rental records")
    (OUT / "tables").mkdir(parents=True, exist_ok=True)
    (OUT / "charts").mkdir(parents=True, exist_ok=True)
    def agg(keys):
        return (df.groupby(keys, observed=True)
                .agg(hourly_records=("cnt", "size"), avg_hourly_rentals=("cnt", "mean"),
                     median_hourly_rentals=("cnt", "median"))
                .reset_index().round(2))
    hours = agg("hr")
    workday_hours = agg(["workingday", "hr"])
    weather = agg("weathersit")
    season = agg("season")
    for name, table in [("hourly_demand", hours), ("workday_hourly_demand", workday_hours),
                        ("demand_by_weather_code", weather), ("demand_by_season_code", season)]:
        table.to_csv(OUT / "tables" / f"{name}.csv", index=False)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(hours["hr"], hours["avg_hourly_rentals"], marker="o")
    ax.set(xlabel="Hour of day (0–23)", ylabel="Average rentals per observed hour", title="Average bike rentals by hour")
    ax.set_xticks(range(0, 24, 2))
    fig.tight_layout(); fig.savefig(OUT / "charts" / "hourly_profile.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for is_workday, part in workday_hours.groupby("workingday"):
        ax.plot(part["hr"], part["avg_hourly_rentals"], marker=".", label="Working day" if is_workday == 1 else "Non-working day")
    ax.set(xlabel="Hour of day", ylabel="Average rentals per observed hour", title="Hour profiles by working day")
    ax.legend(); fig.tight_layout(); fig.savefig(OUT / "charts" / "workday_comparison.png", dpi=150); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.6))
    ax.bar(weather["weathersit"].astype(int).astype(str), weather["avg_hourly_rentals"])
    ax.set(xlabel="Weather category code (see source documentation)", ylabel="Average rentals per observed hour", title="Rental demand by weather category")
    fig.tight_layout(); fig.savefig(OUT / "charts" / "weather_comparison.png", dpi=150); plt.close(fig)
    peak = hours.sort_values("avg_hourly_rentals", ascending=False).iloc[0]
    report = f"""# Findings — The Commuter Rush

- Source rows: {raw_rows:,}; valid hourly records: {len(df):,}.
- Highest average observed hourly demand: **{int(peak['hr']):02d}:00**, averaging **{peak['avg_hourly_rentals']:,.1f} rentals** per observed hour.
- Comparison tables show workday patterns, weather codes, and season codes.

## Interpretation and next step
These are observations from **2011–2012**, not a live demand forecast. Rentals in bad weather may be affected by many confounders. Use the UCI codebook before interpreting category numbers. This dataset is CC BY 4.0; cite Fanaee-T (2013), https://doi.org/10.24432/C5W894.
"""
    (OUT / "findings.md").write_text(report, encoding="utf-8")
    print(f"Done. {len(df):,} hourly observations analyzed. Results: {OUT}")


if __name__ == "__main__":
    main()
