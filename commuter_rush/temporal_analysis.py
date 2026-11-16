from __future__ import annotations

from datetime import datetime
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys

import numpy as np
import pandas as pd

from commuter_rush.monthly_quality import ANALYTICAL_FIELDS

SOURCE_CSV = Path("data/processed/mta_subway_station_hour_october_2024.csv")
SOURCE_MANIFEST = Path("outputs/monthly_acquisition/source_acquisition_manifest.json")
OUTPUT_DIRECTORY = Path("outputs/temporal_analysis")
TABLE_DIRECTORY = Path("portfolio/tables")
REPORT_DIRECTORY = Path("portfolio/reports")
EXPECTED_START = pd.Timestamp("2024-10-01 00:00:00")
EXPECTED_END = pd.Timestamp("2024-11-01 00:00:00")
MORNING_HOURS = (7, 8, 9)
EVENING_HOURS = (16, 17, 18)
MIN_PEAK_COVERAGE = 0.90


class AnalysisError(RuntimeError):
    pass


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json_atomic(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    try:
        temporary.write_text(json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def verify_source(csv_path=SOURCE_CSV, manifest_path=SOURCE_MANIFEST):
    csv_path = Path(csv_path)
    manifest_path = Path(manifest_path)
    if not csv_path.is_file() or not manifest_path.is_file():
        raise AnalysisError("Verified monthly CSV and source manifest are required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    q = manifest.get("month_quality", {})
    digest = manifest.get("processed_csv", {})
    if (manifest.get("dataset_id") != "wujg-7c2s"
            or manifest.get("status") != "month_acquisition_passed"
            or manifest.get("days_completed") != 31
            or q.get("observed_clock_hours") != 744
            or q.get("all_daily_source_controls_reconciled") is not True
            or q.get("station_hour_keys_unique") is not True
            or q.get("source_metadata_conflicts_preserved") is not True
            or q.get("missing_station_hours_not_assumed_zero") is not True):
        raise AnalysisError("Source manifest has not passed monthly quality gates")
    if digest.get("sha256") != file_sha256(csv_path) or digest.get("bytes") != csv_path.stat().st_size:
        raise AnalysisError("Processed monthly CSV differs from its verified source fingerprint")
    if len(manifest.get("daily_snapshot_files", [])) != 31:
        raise AnalysisError("Incomplete daily-source snapshot inventory")
    return manifest


def validated_frame(csv_path, manifest):
    frame = pd.read_csv(
        csv_path,
        dtype={"station_complex_id": "string", "station_complex": "string", "borough": "string", "transit_timestamp": "string"},
        keep_default_na=False,
    )
    if list(frame.columns) != list(ANALYTICAL_FIELDS):
        raise AnalysisError("Unexpected station-hour CSV schema")
    if len(frame) != manifest["month_quality"]["station_hour_rows"]:
        raise AnalysisError("Source station-hour row count mismatch")
    if frame.empty or frame[["transit_timestamp", "station_complex_id", "station_complex", "borough"]].eq("").any().any():
        raise AnalysisError("Missing station-hour identifiers or labels")
    if frame.duplicated(["transit_timestamp", "station_complex_id"]).any():
        raise AnalysisError("Repeated analytical station-hour key")
    try:
        frame["timestamp"] = pd.to_datetime(frame["transit_timestamp"], format="%Y-%m-%dT%H:%M:%S", errors="raise", exact=True)
    except (ValueError, TypeError) as exc:
        raise AnalysisError("Invalid local station-hour timestamps") from exc
    if (frame["timestamp"].min() < EXPECTED_START or frame["timestamp"].max() >= EXPECTED_END
            or frame["timestamp"].dt.minute.ne(0).any() or frame["timestamp"].dt.second.ne(0).any()):
        raise AnalysisError("Station-hours outside frozen local date and hour boundaries")
    expected_hours = pd.date_range(EXPECTED_START, EXPECTED_END, freq="h", inclusive="left")
    observed_hours = pd.DatetimeIndex(frame["timestamp"].unique())
    if not (len(observed_hours) == 744 and observed_hours.sort_values().equals(expected_hours)):
        raise AnalysisError("Study window is missing one or more observed clock hours")
    for name in ("estimated_entries", "included_transfers", "fare_rows"):
        try:
            frame[name] = pd.to_numeric(frame[name], errors="raise")
        except (TypeError, ValueError) as exc:
            raise AnalysisError(f"Invalid numeric field: {name}") from exc
        if not np.isfinite(frame[name].to_numpy(dtype=float)).all() or (frame[name] < 0).any():
            raise AnalysisError(f"Nonfinite or negative values in {name}")
    if (frame["included_transfers"] > frame["estimated_entries"]).any():
        raise AnalysisError("Transfers exceed estimated entries")
    if (frame["fare_rows"] < 1).any() or not (frame["fare_rows"] == frame["fare_rows"].round()).all():
        raise AnalysisError("Invalid underlying fare-row counts")
    if frame["latitude"].eq("").any() != frame["longitude"].eq("").any():
        raise AnalysisError("Partially missing coordinates require review")
    for column in ("latitude", "longitude"):
        frame[column] = pd.to_numeric(frame[column].replace("", np.nan), errors="raise")
    if (frame["latitude"].notna() ^ frame["longitude"].notna()).any():
        raise AnalysisError("One-sided missing coordinates")
    valid_coords = frame["latitude"].notna()
    if ((~frame.loc[valid_coords, "latitude"].between(40, 41.2)).any()
            or (~frame.loc[valid_coords, "longitude"].between(-75, -72.5)).any()):
        raise AnalysisError("Station coordinates outside plausible regional bounds")
    q = manifest["month_quality"]
    checks = (
        ("estimated_entries", "estimated_entries", 0.01),
        ("included_transfers", "included_transfers_subset", 0.01),
        ("fare_rows", "source_fare_rows_reconciled", 0.01),
    )
    for field, expected, tolerance in checks:
        if not math.isclose(float(frame[field].sum()), float(q[expected]), rel_tol=0, abs_tol=tolerance):
            raise AnalysisError(f"Analytical {field} total does not reconcile to MTA source")
    if int(frame["station_complex_id"].nunique()) != int(q["unique_station_complexes"]):
        raise AnalysisError("Station complex inventory does not reconcile")
    frame["date"] = frame["timestamp"].dt.strftime("%Y-%m-%d")
    frame["hour"] = frame["timestamp"].dt.hour
    frame["weekday_number"] = frame["timestamp"].dt.weekday
    frame["weekday"] = frame["timestamp"].dt.day_name()
    frame["day_type"] = np.where(frame["weekday_number"] < 5, "Weekday", "Weekend")
    return frame


def gini_coefficient(values):
    arr = np.sort(np.asarray(values, dtype=float))
    if arr.size == 0 or not np.isfinite(arr).all() or (arr < 0).any():
        raise AnalysisError("Invalid station-level concentration values")
    total = float(arr.sum())
    if total == 0:
        raise AnalysisError("Concentration is undefined for zero total entries")
    n = len(arr)
    return float(2 * np.dot(np.arange(1, n + 1), arr) / (n * total) - (n + 1) / n)


def representative_station_labels(frame):
    metadata = (
        frame.groupby(["station_complex_id", "station_complex", "borough"], observed=True)
        .size().rename("observed_rows").reset_index()
    )
    metadata = metadata.sort_values(
        ["station_complex_id", "observed_rows", "station_complex", "borough"],
        ascending=[True, False, True, True], kind="mergesort",
    )
    return metadata.drop_duplicates("station_complex_id")[["station_complex_id", "station_complex", "borough"]]


def build_tables(frame):
    labels = representative_station_labels(frame)
    daily = frame.groupby(["date", "weekday_number", "weekday", "day_type"], as_index=False).agg(
        estimated_entries=("estimated_entries", "sum"),
        included_transfers=("included_transfers", "sum"),
        observed_station_hours=("station_complex_id", "size"),
        reporting_stations=("station_complex_id", "nunique"),
    ).sort_values("date")
    day_hour = frame.groupby(["date", "weekday_number", "weekday", "day_type", "hour"], as_index=False).agg(
        estimated_entries=("estimated_entries", "sum"),
        reporting_stations=("station_complex_id", "nunique"),
    )
    hourly = day_hour.groupby(["day_type", "hour"], as_index=False).agg(
        mean_entries_per_day=("estimated_entries", "mean"),
        median_entries_per_day=("estimated_entries", "median"),
        mean_reporting_stations=("reporting_stations", "mean"),
        observed_days=("date", "nunique"),
    ).sort_values(["day_type", "hour"])
    weekday_hour = day_hour.groupby(["weekday_number", "weekday", "hour"], as_index=False).agg(
        mean_entries_per_day=("estimated_entries", "mean"),
        observed_days=("date", "nunique"),
    ).sort_values(["weekday_number", "hour"])
    borough = frame.groupby("borough", as_index=False).agg(
        estimated_entries=("estimated_entries", "sum"),
        included_transfers=("included_transfers", "sum"),
        observed_station_hours=("station_complex_id", "size"),
        station_complexes=("station_complex_id", "nunique"),
    ).sort_values("estimated_entries", ascending=False)
    borough["system_entry_share_pct"] = 100 * borough["estimated_entries"] / borough["estimated_entries"].sum()
    station = frame.groupby("station_complex_id", as_index=False).agg(
        estimated_entries=("estimated_entries", "sum"),
        observed_hours=("timestamp", "nunique"),
    ).merge(labels, on="station_complex_id", how="left", validate="one_to_one")
    station["observed_hour_coverage_pct"] = 100 * station["observed_hours"] / 744
    station = station.sort_values(["estimated_entries", "station_complex_id"], ascending=[False, True]).reset_index(drop=True)
    station["rank"] = np.arange(1, len(station) + 1)
    station["system_entry_share_pct"] = 100 * station["estimated_entries"] / station["estimated_entries"].sum()
    station["cumulative_system_share_pct"] = station["system_entry_share_pct"].cumsum()
    weekdays = frame[frame["weekday_number"] < 5].copy()
    n_weekdays = int(daily["day_type"].eq("Weekday").sum())
    if n_weekdays < 2:
        raise AnalysisError("Insufficient weekday observations")
    weekdays["window"] = np.select(
        [weekdays["hour"].isin(MORNING_HOURS), weekdays["hour"].isin(EVENING_HOURS)],
        ["morning", "evening"], default="other",
    )
    weekday_borough = weekdays.groupby("borough", as_index=False)["estimated_entries"].sum().rename(
        columns={"estimated_entries": "all_weekday_entries"}
    )
    peak_borough = weekdays[weekdays["window"] != "other"].pivot_table(
        index="borough", columns="window", values="estimated_entries", aggfunc="sum", fill_value=0, observed=True,
    ).reset_index()
    for col in ("morning", "evening"):
        if col not in peak_borough:
            peak_borough[col] = 0.0
    peak_borough = weekday_borough.merge(peak_borough[["borough", "morning", "evening"]], on="borough", validate="one_to_one")
    peak_borough["morning_share_of_borough_weekday_pct"] = 100 * peak_borough["morning"] / peak_borough["all_weekday_entries"]
    peak_borough["evening_share_of_borough_weekday_pct"] = 100 * peak_borough["evening"] / peak_borough["all_weekday_entries"]
    peak_borough = peak_borough.sort_values("all_weekday_entries", ascending=False)
    peak_rows = weekdays[weekdays["window"] != "other"].groupby(["station_complex_id", "window"], as_index=False).agg(
        estimated_entries=("estimated_entries", "sum"),
        observed_station_hours=("timestamp", "nunique"),
    )
    peak_entries = peak_rows.pivot(index="station_complex_id", columns="window", values="estimated_entries").fillna(0)
    peak_counts = peak_rows.pivot(index="station_complex_id", columns="window", values="observed_station_hours").fillna(0)
    for col in ("morning", "evening"):
        if col not in peak_entries:
            peak_entries[col] = 0.0
            peak_counts[col] = 0
    station_peak = pd.DataFrame({
        "station_complex_id": peak_entries.index,
        "morning_entries": peak_entries["morning"].to_numpy(),
        "evening_entries": peak_entries["evening"].to_numpy(),
        "observed_morning_hours": peak_counts["morning"].to_numpy(),
        "observed_evening_hours": peak_counts["evening"].to_numpy(),
    }).merge(labels, on="station_complex_id", how="left", validate="one_to_one")
    possible = n_weekdays * 3
    station_peak["morning_coverage_pct"] = 100 * station_peak["observed_morning_hours"] / possible
    station_peak["evening_coverage_pct"] = 100 * station_peak["observed_evening_hours"] / possible
    station_peak["eligible_for_peak_ranking"] = (
        (station_peak["morning_coverage_pct"] >= MIN_PEAK_COVERAGE * 100)
        & (station_peak["evening_coverage_pct"] >= MIN_PEAK_COVERAGE * 100)
    )
    station_peak["larger_peak_window"] = np.select(
        [station_peak["morning_entries"] > station_peak["evening_entries"], station_peak["evening_entries"] > station_peak["morning_entries"]],
        ["morning", "evening"], default="equal",
    )
    station_peak = station_peak.sort_values(["morning_entries", "station_complex_id"], ascending=[False, True])
    eligible = station_peak[station_peak["eligible_for_peak_ranking"]].copy()
    if eligible.empty:
        raise AnalysisError("No stations satisfy the preregistered peak coverage threshold")
    top_morning = eligible.sort_values(["morning_entries", "station_complex_id"], ascending=[False, True]).head(15)
    top_evening = eligible.sort_values(["evening_entries", "station_complex_id"], ascending=[False, True]).head(15)
    day_type_summary = daily.groupby("day_type", as_index=False).agg(
        days=("date", "nunique"),
        mean_daily_entries=("estimated_entries", "mean"),
        median_daily_entries=("estimated_entries", "median"),
        total_entries=("estimated_entries", "sum"),
        minimum_reporting_stations=("reporting_stations", "min"),
        maximum_reporting_stations=("reporting_stations", "max"),
    )
    tables = {
        "daily_entry_summary": daily,
        "hourly_daytype_profiles": hourly,
        "weekday_hourly_profiles": weekday_hour,
        "borough_entry_summary": borough,
        "borough_weekday_peak_shares": peak_borough,
        "station_entry_concentration": station,
        "station_weekday_peak_profiles": station_peak,
        "top_weekday_morning_stations": top_morning,
        "top_weekday_evening_stations": top_evening,
        "daytype_entry_summary": day_type_summary,
    }
    if not math.isclose(float(daily["estimated_entries"].sum()), float(frame["estimated_entries"].sum()), rel_tol=0, abs_tol=0.01):
        raise AnalysisError("Daily aggregate totals did not reconcile")
    if not math.isclose(float(borough["estimated_entries"].sum()), float(frame["estimated_entries"].sum()), rel_tol=0, abs_tol=0.01):
        raise AnalysisError("Borough aggregate totals did not reconcile")
    if not math.isclose(float(station["estimated_entries"].sum()), float(frame["estimated_entries"].sum()), rel_tol=0, abs_tol=0.01):
        raise AnalysisError("Station aggregate totals did not reconcile")
    return tables


def result_summary(frame, tables, source_manifest):
    daily = tables["daily_entry_summary"]
    profiles = tables["hourly_daytype_profiles"]
    station = tables["station_entry_concentration"]
    peaks = tables["station_weekday_peak_profiles"]
    weekdays = frame[frame["weekday_number"] < 5]
    morning = float(weekdays.loc[weekdays["hour"].isin(MORNING_HOURS), "estimated_entries"].sum())
    evening = float(weekdays.loc[weekdays["hour"].isin(EVENING_HOURS), "estimated_entries"].sum())
    weekday_total = float(weekdays["estimated_entries"].sum())
    weekday_peak_profile = profiles[profiles["day_type"].eq("Weekday")]
    largest_hour = weekday_peak_profile.loc[weekday_peak_profile["mean_entries_per_day"].idxmax()]
    all_entries = float(frame["estimated_entries"].sum())
    top10_share = float(station.head(10)["estimated_entries"].sum() / all_entries * 100)
    q = source_manifest["month_quality"]
    return {
        "source_dataset_id": "wujg-7c2s",
        "source_csv_sha256": source_manifest["processed_csv"]["sha256"],
        "study_month": "2024-10",
        "local_timezone": "America/New_York; original local timestamps without offset",
        "observed_station_hours": int(len(frame)),
        "observed_station_complexes": int(station.shape[0]),
        "observed_clock_hours": int(frame["timestamp"].nunique()),
        "calendar_days": int(daily.shape[0]),
        "weekday_days": int(daily["day_type"].eq("Weekday").sum()),
        "weekend_days": int(daily["day_type"].eq("Weekend").sum()),
        "estimated_entries": all_entries,
        "transfers_included_subset": float(frame["included_transfers"].sum()),
        "source_fare_records": int(frame["fare_rows"].sum()),
        "coordinate_variant_station_hours_in_source": int(q["station_hours_with_coordinate_variants"]),
        "distinct_stations_with_changing_metadata": int(q["station_ids_with_multiple_metadata_variants"]),
        "observed_hour_station_count_min": int(frame.groupby("timestamp")["station_complex_id"].nunique().min()),
        "observed_hour_station_count_max": int(frame.groupby("timestamp")["station_complex_id"].nunique().max()),
        "weekday_morning_entries": morning,
        "weekday_evening_entries": evening,
        "weekday_morning_share_pct": 100 * morning / weekday_total,
        "weekday_evening_share_pct": 100 * evening / weekday_total,
        "highest_mean_weekday_hour_local": int(largest_hour["hour"]),
        "highest_mean_weekday_hour_entries": float(largest_hour["mean_entries_per_day"]),
        "top_10_station_share_pct": top10_share,
        "station_entry_gini": gini_coefficient(station["estimated_entries"]),
        "peak_ranking_minimum_observed_hours_pct": MIN_PEAK_COVERAGE * 100,
        "peak_ranking_eligible_station_complexes": int(peaks["eligible_for_peak_ranking"].sum()),
        "peak_ranking_excluded_station_complexes": int((~peaks["eligible_for_peak_ranking"]).sum()),
        "missing_station_hours_imputed_as_zero": False,
        "station_hour_metadata_rule": source_manifest.get("metadata_policy", "Station-hour source metadata variants audited at acquisition"),
    }


def output_report(summary, tables):
    daily = tables["daytype_entry_summary"].set_index("day_type")
    weekday = daily.loc["Weekday"]
    weekend = daily.loc["Weekend"]
    return "\n".join([
        "# October 2024 subway entry patterns — descriptive findings",
        "",
        "**Author:** Cyril James Lunzaga",
        "**Data owner:** Metropolitan Transportation Authority (MTA)",
        "**Source:** [MTA Subway Hourly Ridership: 2020–2024](https://data.ny.gov/d/wujg-7c2s)",
        "**Scope:** October 1–31, 2024, New York local clock time; subway station-complex hourly estimated entries",
        "",
        "## Verified study footprint",
        "",
        f"- {summary['observed_station_hours']:,} unique station-hours across {summary['observed_station_complexes']:,} complexes, 31 calendar days, and 744 observed clock hours.",
        f"- {summary['estimated_entries']:,.0f} estimated entries; the {summary['transfers_included_subset']:,.0f} transfer subset is already included and is not added to this total.",
        f"- {summary['coordinate_variant_station_hours_in_source']:,} source station-hours had coordinate metadata variants; the acquisition retained an audit of both source-group values and the representative display coordinate.",
        "",
        "## Descriptive demand structure",
        "",
        f"- Mean estimated entries per weekday: {weekday['mean_daily_entries']:,.0f} ({int(weekday['days'])} weekdays); mean per weekend day: {weekend['mean_daily_entries']:,.0f} ({int(weekend['days'])} weekend days). These are descriptive comparisons, not causal effects.",
        f"- Across weekdays, 07:00–09:59 contributes {summary['weekday_morning_share_pct']:.2f}% and 16:00–18:59 contributes {summary['weekday_evening_share_pct']:.2f}% of observed weekday estimated entries. Both windows have three clock hours per day.",
        f"- The highest mean systemwide weekday entry hour begins at {summary['highest_mean_weekday_hour_local']:02d}:00, with {summary['highest_mean_weekday_hour_entries']:,.0f} estimated entries per weekday on average.",
        f"- The 10 highest-volume station complexes contribute {summary['top_10_station_share_pct']:.2f}% of October estimated entries. Station-level entry Gini: {summary['station_entry_gini']:.3f}.",
        f"- {summary['peak_ranking_eligible_station_complexes']} station complexes pass the predefined >=90% observed-hour requirement in both peak windows; {summary['peak_ranking_excluded_station_complexes']} are excluded from primary peak ranking, not from the systemwide entry totals.",
        "",
        "## Interpretation and limits",
        "",
        "Observed entries are modeled fare-paid station entries, not unique commuter trips, vehicle crowding, queue length, delay, or passenger origin-destination paths. A missing station-hour is not automatically zero. Day-type averages use each calendar day as an observation so a 23-weekday versus 8-weekend month does not inflate weekday hourly averages. We make no inference about long-run seasonality from one month. Station coordinates are representative display metadata with documented source inconsistencies; they are not authoritative geocoding.",
        "",
        "All figures and tables are directly generated from the locally validated 2024-10 station-hour CSV. Inferential uncertainty and station clustering are reserved for separately reviewed later phases.",
        "",
    ])


def write_tables(tables, destination=TABLE_DIRECTORY):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {}
    for key, table in tables.items():
        path = destination / f"{key}.csv"
        temporary = path.with_suffix(".csv.partial")
        try:
            table.to_csv(temporary, index=False, float_format="%.8f", lineterminator="\n")
            os.replace(temporary, path)
        finally:
            if temporary.exists():
                temporary.unlink()
        paths[key] = {"path": path.as_posix(), "sha256": file_sha256(path), "rows": int(len(table))}
    return paths


def main(argv=None):
    parser = argparse.ArgumentParser(description="Reconciled October 2024 MTA descriptive station-hour analysis")
    parser.add_argument("--csv", default=str(SOURCE_CSV))
    parser.add_argument("--source-manifest", default=str(SOURCE_MANIFEST))
    args = parser.parse_args(argv)
    try:
        manifest = verify_source(args.csv, args.source_manifest)
        frame = validated_frame(args.csv, manifest)
        tables = build_tables(frame)
        summary = result_summary(frame, tables, manifest)
        artifacts = write_tables(tables)
        write_json_atomic(OUTPUT_DIRECTORY / "descriptive_summary.json", summary)
        report = output_report(summary, tables)
        REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
        report_path = REPORT_DIRECTORY / "october_descriptive_findings.md"
        report_path.write_text(report, encoding="utf-8", newline="\n")
        write_json_atomic(OUTPUT_DIRECTORY / "descriptive_artifacts.json", {
            "source_csv_sha256": manifest["processed_csv"]["sha256"],
            "tables": artifacts,
            "report": {"path": report_path.as_posix(), "sha256": file_sha256(report_path)},
        })
    except (AnalysisError, OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"STOP - Temporal analysis did not pass: {exc}", file=sys.stderr)
        return 2
    print(f"PASS - Descriptive analysis: {summary['observed_station_hours']:,} station-hours, {summary['estimated_entries']:,.0f} estimated entries")
    print(f"PASS - {len(artifacts)} curated descriptive tables, one evidence-based report")
    print(f"RESULT - Weekday morning share: {summary['weekday_morning_share_pct']:.2f}%")
    print(f"RESULT - Weekday evening share: {summary['weekday_evening_share_pct']:.2f}%")
    print(f"RESULT - Highest mean weekday hour begins: {summary['highest_mean_weekday_hour_local']:02d}:00")
    print(f"RESULT - Top-ten station entry share: {summary['top_10_station_share_pct']:.2f}%")
    print("SCOPE - Descriptive patterns only; no statistical inference or crowding claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
