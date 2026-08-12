"""Figures (plan §8.1, Scores and Maps & case studies steps). Every function returns a
matplotlib Figure; the app layer decides whether to embed it (report) or serve it as a
downloadable PNG.

Style: the workspace's own graph style guide (_system/graphs/) is not populated yet, so
this uses clean, colourblind-safe seaborn/matplotlib defaults (seaborn "ticks" style,
seaborn "colorblind" palette). Swap in the real house style once that reference exists.

Maps use cartopy for coastlines/borders when the Natural Earth shapefiles are available
(cached locally after one online fetch — see README "Known limitations" for what that
means for a partner machine that has never had a network connection); otherwise they
fall back to a plain lat/lon grid with no basemap, so map-making never hard-fails offline.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import seaborn as sns
import xarray as xr
from matplotlib.figure import Figure

from engine.bootstrap import BootstrapResult
from engine.scores import RankHistogram, ReliabilityDiagram, RocCurve

sns.set_theme(style="ticks", palette="colorblind")

_GOOD_COLOR = "#2b7a4b"
_BAD_COLOR = "#b23a48"
_NEUTRAL_COLOR = "#4c72b0"


def _new_fig(figsize=(6, 4.5)) -> tuple[Figure, "plt.Axes"]:
    fig = Figure(figsize=figsize, dpi=120)
    ax = fig.add_subplot(111)
    return fig, ax


def plot_crps_by_lead(results_by_lead: dict[int, BootstrapResult]) -> Figure:
    fig, ax = _new_fig()
    leads = sorted(results_by_lead)
    means = [results_by_lead[l].estimate for l in leads]
    los = [results_by_lead[l].estimate - results_by_lead[l].ci_low for l in leads]
    his = [results_by_lead[l].ci_high - results_by_lead[l].estimate for l in leads]
    ax.errorbar(leads, means, yerr=[los, his], fmt="o-", color=_NEUTRAL_COLOR, capsize=4)
    for l in leads:
        if results_by_lead[l].small_sample_warning:
            ax.annotate("n<30", (l, results_by_lead[l].estimate), textcoords="offset points",
                        xytext=(6, 6), fontsize=8, color=_BAD_COLOR)
    ax.set_xlabel("Lead day")
    ax.set_ylabel("CRPS (mm)")
    ax.set_title("CRPS by lead time (95% CI, moving-block bootstrap)")
    ax.set_xticks(leads)
    sns.despine(fig)
    return fig


def plot_rank_histogram(rh: RankHistogram) -> Figure:
    fig, ax = _new_fig()
    ranks = np.arange(1, len(rh.counts) + 1)
    expected = rh.counts.sum() / len(rh.counts)
    ax.bar(ranks, rh.counts, color=_NEUTRAL_COLOR, edgecolor="white")
    ax.axhline(expected, color=_BAD_COLOR, linestyle="--", label=f"Flat (expected {expected:.1f})")
    ax.set_xlabel("Rank")
    ax.set_ylabel("Count")
    ax.set_title(f"Rank histogram (χ²={rh.chi2_statistic:.1f}, p={rh.p_value:.3f})")
    ax.legend(frameon=False)
    sns.despine(fig)
    return fig


def plot_reliability_diagram(rd: ReliabilityDiagram, threshold_mm: float) -> Figure:
    fig = Figure(figsize=(6, 6), dpi=120)
    ax = fig.add_axes([0.15, 0.35, 0.8, 0.55])
    ax_sharp = fig.add_axes([0.15, 0.1, 0.8, 0.18], sharex=ax)

    valid = ~np.isnan(rd.mean_forecast_prob)
    ax.plot([0, 1], [0, 1], "--", color="grey", label="Perfectly reliable")
    ax.plot(rd.mean_forecast_prob[valid], rd.observed_frequency[valid], "o-", color=_NEUTRAL_COLOR)
    ax.set_ylabel("Observed frequency")
    ax.set_title(f"Reliability diagram (>= {threshold_mm} mm)")
    ax.legend(frameon=False, loc="upper left")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    bin_centers = (rd.bin_edges[:-1] + rd.bin_edges[1:]) / 2
    ax_sharp.bar(bin_centers, rd.sample_count, width=(rd.bin_edges[1] - rd.bin_edges[0]) * 0.9,
                 color=_NEUTRAL_COLOR)
    small = rd.sample_count < 30
    if small.any():
        ax_sharp.bar(bin_centers[small], rd.sample_count[small],
                     width=(rd.bin_edges[1] - rd.bin_edges[0]) * 0.9, color=_BAD_COLOR,
                     label="n<30")
        ax_sharp.legend(frameon=False, fontsize=8)
    ax_sharp.set_xlabel("Forecast probability")
    ax_sharp.set_ylabel("N")
    sns.despine(fig)
    return fig


def plot_roc_curve(roc: RocCurve, threshold_mm: float) -> Figure:
    fig, ax = _new_fig()
    ax.plot([0, 1], [0, 1], "--", color="grey", label="No skill")
    ax.plot(roc.pofd, roc.pod, "o-", color=_NEUTRAL_COLOR, label=f"AUC={roc.auc:.3f}")
    ax.set_xlabel("Probability of false detection")
    ax.set_ylabel("Probability of detection")
    ax.set_title(f"ROC curve (>= {threshold_mm} mm)")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.legend(frameon=False, loc="lower right")
    sns.despine(fig)
    return fig


def plot_bss_by_threshold(bss_by_threshold: dict[float, float]) -> Figure:
    fig, ax = _new_fig()
    thresholds = sorted(bss_by_threshold)
    values = [bss_by_threshold[t] for t in thresholds]
    colors = [_GOOD_COLOR if v >= 0 else _BAD_COLOR for v in values]
    ax.bar([str(t) for t in thresholds], values, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xlabel("Threshold (mm/24h)")
    ax.set_ylabel("Brier Skill Score")
    ax.set_title("BSS by threshold (vs sample climatology)")
    sns.despine(fig)
    return fig


def plot_spread_error_by_lead(spread_by_lead: dict[int, float], rmse_by_lead: dict[int, float]) -> Figure:
    fig, ax = _new_fig()
    leads = sorted(spread_by_lead)
    ax.plot(leads, [spread_by_lead[l] for l in leads], "o-", label="Ensemble spread", color=_NEUTRAL_COLOR)
    ax.plot(leads, [rmse_by_lead[l] for l in leads], "s--", label="RMSE of ensemble mean", color=_BAD_COLOR)
    ax.set_xlabel("Lead day")
    ax.set_ylabel("mm")
    ax.set_title("Spread vs error by lead")
    ax.set_xticks(leads)
    ax.legend(frameon=False)
    sns.despine(fig)
    return fig


# --------------------------------------------------------------------------------------
# Maps
# --------------------------------------------------------------------------------------

def _map_axes(fig: Figure, rect: tuple[float, float, float, float], extent: tuple[float, float, float, float]):
    """Add a map axes with coastlines if cartopy's basemap data is available (cached
    locally after one online fetch); otherwise a plain lat/lon axes, so this never hard
    fails on an offline machine that has never fetched Natural Earth data.
    """
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        ax = fig.add_axes(rect, projection=ccrs.PlateCarree())
        ax.set_extent(extent, crs=ccrs.PlateCarree())
        ax.add_feature(cfeature.COASTLINE, linewidth=0.6)
        ax.add_feature(cfeature.BORDERS, linewidth=0.4, linestyle=":")
        ax.gridlines(draw_labels=True, linewidth=0.3, alpha=0.5)
        return ax, ccrs.PlateCarree()
    except Exception:
        ax = fig.add_axes(rect)
        ax.set_xlim(extent[0], extent[1])
        ax.set_ylim(extent[2], extent[3])
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.text(0.02, 0.98, "basemap unavailable offline", transform=ax.transAxes,
                va="top", fontsize=7, color=_BAD_COLOR)
        return ax, None


def map_ensemble_mean(forecast: xr.Dataset, ref_time, lead_day: int,
                       obs: pd.DataFrame | None = None) -> Figure:
    field = forecast["tp"].sel(forecast_reference_time=ref_time, lead_day=lead_day).mean("member")
    lat, lon = forecast["lat"].values, forecast["lon"].values
    extent = (lon.min(), lon.max(), lat.min(), lat.max())

    fig = Figure(figsize=(7, 6), dpi=120)
    ax, crs = _map_axes(fig, [0.1, 0.1, 0.75, 0.8], extent)
    kwargs = {"transform": crs} if crs is not None else {}
    mesh = ax.pcolormesh(lon, lat, field.values, cmap="Blues", shading="auto", **kwargs)
    if obs is not None and len(obs):
        ax.scatter(obs["lon"], obs["lat"], c=obs["precip_mm"], cmap="Blues", edgecolor="black",
                    linewidth=0.5, s=40, vmin=float(field.min()), vmax=float(field.max()), **kwargs)
    cax = fig.add_axes([0.87, 0.15, 0.03, 0.7])
    fig.colorbar(mesh, cax=cax, label="Ensemble mean (mm/24h)")
    ax.set_title(f"Ensemble mean — lead {lead_day}d, ref {pd.Timestamp(ref_time).date()}")
    return fig


def map_exceedance_probability(forecast: xr.Dataset, ref_time, lead_day: int, threshold_mm: float,
                                obs: pd.DataFrame | None = None) -> Figure:
    members = forecast["tp"].sel(forecast_reference_time=ref_time, lead_day=lead_day)
    prob = (members >= threshold_mm).mean("member")
    lat, lon = forecast["lat"].values, forecast["lon"].values
    extent = (lon.min(), lon.max(), lat.min(), lat.max())

    fig = Figure(figsize=(7, 6), dpi=120)
    ax, crs = _map_axes(fig, [0.1, 0.1, 0.75, 0.8], extent)
    kwargs = {"transform": crs} if crs is not None else {}
    mesh = ax.pcolormesh(lon, lat, prob.values, cmap="YlOrRd", vmin=0, vmax=1, shading="auto", **kwargs)
    if obs is not None and len(obs):
        exceeded = obs["precip_mm"] >= threshold_mm
        ax.scatter(obs.loc[~exceeded, "lon"], obs.loc[~exceeded, "lat"], marker="o", facecolor="none",
                    edgecolor="black", s=30, **kwargs)
        ax.scatter(obs.loc[exceeded, "lon"], obs.loc[exceeded, "lat"], marker="o", facecolor="black",
                    edgecolor="white", s=30, **kwargs)
    cax = fig.add_axes([0.87, 0.15, 0.03, 0.7])
    fig.colorbar(mesh, cax=cax, label=f"P(precip >= {threshold_mm}mm)")
    ax.set_title(f"Exceedance probability — lead {lead_day}d, ref {pd.Timestamp(ref_time).date()}")
    return fig


def map_postage_stamp(forecast: xr.Dataset, ref_time, lead_day: int, max_members: int = 12) -> Figure:
    members = forecast["tp"].sel(forecast_reference_time=ref_time, lead_day=lead_day)
    n = min(max_members, members.sizes["member"])
    lat, lon = forecast["lat"].values, forecast["lon"].values
    vmax = float(members.isel(member=slice(0, n)).max())

    ncols = int(np.ceil(np.sqrt(n)))
    nrows = int(np.ceil(n / ncols))
    fig = Figure(figsize=(2.2 * ncols, 2.0 * nrows), dpi=110)
    for i in range(n):
        ax = fig.add_subplot(nrows, ncols, i + 1)
        ax.pcolormesh(lon, lat, members.isel(member=i).values, cmap="Blues", vmin=0, vmax=vmax, shading="auto")
        ax.set_title(f"m{int(members['member'].values[i])}", fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
    fig.suptitle(f"Postage-stamp members — lead {lead_day}d, ref {pd.Timestamp(ref_time).date()}")
    return fig


def save_png(fig: Figure, path) -> None:
    fig.savefig(path, bbox_inches="tight")
