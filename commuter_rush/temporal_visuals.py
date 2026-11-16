from __future__ import annotations

from pathlib import Path
import argparse
from datetime import timedelta
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from commuter_rush.temporal_analysis import AnalysisError, OUTPUT_DIRECTORY, TABLE_DIRECTORY, file_sha256, write_json_atomic

FIGURE_DIRECTORY = Path("portfolio/figures")
BLUE = "#22577A"
ORANGE = "#DB7731"
TEAL = "#278C88"
GRID = "#E7EBEF"
INK = "#20313E"


def apply_axis_style(axis, y_label):
    axis.set_ylabel(y_label, color=INK)
    axis.grid(axis="y", color=GRID, linewidth=0.8)
    axis.set_axisbelow(True)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.tick_params(axis="both", colors=INK)
    axis.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{value / 1_000_000:.1f}m" if abs(value) >= 1_000_000 else f"{value:,.0f}"))


def save_figure(name, figure, destination):
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{name}.png"
    figure.savefig(path, dpi=160, bbox_inches="tight", facecolor="white", metadata={"Software": "Matplotlib"})
    plt.close(figure)
    return path


def daily_entries_chart(daily, destination):
    plot = daily.copy()
    plot["date"] = pd.to_datetime(plot["date"])
    fig, ax = plt.subplots(figsize=(11.5, 4.7))
    for date in plot.loc[plot["day_type"].eq("Weekend"), "date"]:
        ax.axvspan(date - timedelta(hours=12), date + timedelta(hours=12), color="#F4F0E8", zorder=0)
    ax.plot(plot["date"], plot["estimated_entries"], color=BLUE, linewidth=2.1, marker="o", markersize=3.4)
    ax.set_title("Daily estimated subway entries | October 2024", loc="left", color=INK, fontsize=14, pad=16)
    ax.xaxis.set_major_locator(mdates.DayLocator(interval=3))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.set_xlim(plot["date"].min() - timedelta(hours=12), plot["date"].max() + timedelta(hours=12))
    apply_axis_style(ax, "Estimated station entries")
    ax.text(0, -0.17, "Shaded dates are Saturdays and Sundays. Source: MTA; estimated entries, not individual trips.", transform=ax.transAxes, fontsize=9, color="#536674")
    fig.tight_layout()
    return save_figure("daily_entry_timeline", fig, destination)


def hourly_daytype_chart(hourly, destination):
    fig, ax = plt.subplots(figsize=(10.6, 5.0))
    for day_type, color in (("Weekday", BLUE), ("Weekend", ORANGE)):
        data = hourly[hourly["day_type"].eq(day_type)].sort_values("hour")
        ax.plot(data["hour"], data["mean_entries_per_day"], color=color, linewidth=2.4, marker="o", markersize=3.4, label=day_type)
    ax.axvspan(6.5, 9.5, alpha=0.08, color=TEAL)
    ax.axvspan(15.5, 18.5, alpha=0.08, color=ORANGE)
    ax.set_xticks(list(range(0, 24, 2)))
    ax.set_xlim(0, 23)
    ax.set_xlabel("New York local clock hour (hour beginning)")
    ax.set_title("Average systemwide entries by hour and day type", loc="left", color=INK, fontsize=14, pad=16)
    apply_axis_style(ax, "Mean estimated entries per calendar day")
    ax.legend(frameon=False, loc="upper left")
    ax.text(0, -0.17, "Means are normalized by observed days in each group (23 weekdays; 8 weekends).", transform=ax.transAxes, fontsize=9, color="#536674")
    fig.tight_layout()
    return save_figure("hourly_daytype_demand", fig, destination)


def weekday_hour_heatmap(weekday_hour, destination):
    ordered = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    pivot = weekday_hour.pivot(index="weekday", columns="hour", values="mean_entries_per_day").reindex(index=ordered, columns=range(24))
    if pivot.isna().any().any():
        raise AnalysisError("Incomplete weekday/hour heatmap matrix")
    fig, ax = plt.subplots(figsize=(12.2, 4.4))
    image = ax.imshow(pivot.to_numpy(dtype=float) / 1000, aspect="auto", cmap="YlGnBu", interpolation="nearest")
    ax.set_yticks(range(7), ordered)
    ax.set_xticks(range(24), [f"{hour:02d}" for hour in range(24)])
    ax.set_xlabel("New York local clock hour")
    ax.set_title("Mean systemwide entries by weekday and hour", loc="left", color=INK, fontsize=14, pad=16)
    fig.colorbar(image, ax=ax, shrink=0.90, label="Thousand estimated entries / day")
    fig.tight_layout()
    return save_figure("weekday_hour_heatmap", fig, destination)


def borough_peak_chart(borough_peak, destination):
    data = borough_peak.sort_values("all_weekday_entries", ascending=True)
    y = np.arange(len(data))
    fig, ax = plt.subplots(figsize=(9.8, 4.7))
    ax.barh(y - 0.19, data["morning_share_of_borough_weekday_pct"], height=0.37, color=BLUE, label="07:00–09:59")
    ax.barh(y + 0.19, data["evening_share_of_borough_weekday_pct"], height=0.37, color=ORANGE, label="16:00–18:59")
    ax.set_yticks(y, data["borough"])
    ax.set_xlabel("Share of each borough's observed weekday estimated entries (%)")
    ax.set_title("Morning and evening entry shares within each borough", loc="left", color=INK, fontsize=14, pad=16)
    ax.xaxis.grid(True, color=GRID)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
    fig.tight_layout()
    return save_figure("borough_weekday_peak_shares", fig, destination)


def top_station_chart(station, destination):
    data = station.head(12).sort_values("estimated_entries")
    labels = data.apply(lambda item: f"{item['station_complex_id']}  {item['station_complex']}", axis=1).map(lambda item: item if len(item) <= 43 else item[:40] + "...")
    fig, ax = plt.subplots(figsize=(11.0, 6.2))
    ax.barh(range(len(data)), data["estimated_entries"], color=TEAL)
    ax.set_yticks(range(len(data)), labels)
    ax.set_xlabel("October estimated station entries")
    ax.set_title("Highest-volume station complexes | October 2024", loc="left", color=INK, fontsize=14, pad=16)
    ax.set_ylabel("Station complex", color=INK)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{value / 1_000_000:.1f}m" if abs(value) >= 1_000_000 else f"{value:,.0f}"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color=GRID)
    fig.tight_layout()
    return save_figure("highest_volume_station_complexes", fig, destination)


def station_concentration_chart(station, destination):
    values = np.sort(station["estimated_entries"].to_numpy(dtype=float))
    fractions = np.concatenate(([0.0], np.cumsum(values) / values.sum()))
    stations = np.linspace(0, 1, len(fractions))
    fig, ax = plt.subplots(figsize=(7.3, 6.0))
    ax.plot(stations * 100, fractions * 100, linewidth=2.6, color=BLUE, label="Observed entry concentration")
    ax.plot([0, 100], [0, 100], linestyle="--", color="#8293A0", linewidth=1.4, label="Equal station shares")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Cumulative share of station complexes (least to most entries, %)")
    ax.set_ylabel("Cumulative share of estimated entries (%)")
    ax.set_title("Distribution of October entries across station complexes", loc="left", color=INK, fontsize=13, pad=16)
    ax.grid(True, color=GRID)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    return save_figure("station_entry_concentration_curve", fig, destination)


def verified_tables(index_path=OUTPUT_DIRECTORY / "descriptive_artifacts.json"):
    path = Path(index_path)
    if not path.is_file():
        raise AnalysisError("Descriptive analysis index missing; run temporal_analysis first")
    index = json.loads(path.read_text(encoding="utf-8"))
    expected = (
        "daily_entry_summary", "hourly_daytype_profiles", "weekday_hourly_profiles",
        "borough_weekday_peak_shares", "station_entry_concentration",
    )
    tables = {}
    for name in expected:
        record = index.get("tables", {}).get(name)
        if not isinstance(record, dict):
            raise AnalysisError(f"Missing descriptive table index: {name}")
        file = TABLE_DIRECTORY / f"{name}.csv"
        if record.get("path") != file.as_posix() or not file.is_file() or file_sha256(file) != record.get("sha256"):
            raise AnalysisError(f"Descriptive table fingerprint mismatch: {name}")
        tables[name] = pd.read_csv(file)
    return tables


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render original MTA October 2024 demand visualizations")
    parser.parse_args(argv)
    try:
        tables = verified_tables()
        plt.rcParams.update({"font.size": 10, "axes.titlesize": 13, "axes.labelsize": 10})
        figures = {
            "daily_entry_timeline": daily_entries_chart(tables["daily_entry_summary"], FIGURE_DIRECTORY),
            "hourly_daytype_demand": hourly_daytype_chart(tables["hourly_daytype_profiles"], FIGURE_DIRECTORY),
            "weekday_hour_heatmap": weekday_hour_heatmap(tables["weekday_hourly_profiles"], FIGURE_DIRECTORY),
            "borough_weekday_peak_shares": borough_peak_chart(tables["borough_weekday_peak_shares"], FIGURE_DIRECTORY),
            "highest_volume_station_complexes": top_station_chart(tables["station_entry_concentration"], FIGURE_DIRECTORY),
            "station_entry_concentration_curve": station_concentration_chart(tables["station_entry_concentration"], FIGURE_DIRECTORY),
        }
        write_json_atomic(OUTPUT_DIRECTORY / "visual_artifacts.json", {
            "figures": {name: {"path": file.as_posix(), "sha256": file_sha256(file), "bytes": file.stat().st_size} for name, file in figures.items()}
        })
    except (AnalysisError, OSError, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"STOP - Temporal figures not verified: {exc}", file=sys.stderr)
        return 2
    print(f"PASS - {len(figures)} source-backed descriptive figures generated")
    print("SCOPE - Review all figures visually before Git publication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
