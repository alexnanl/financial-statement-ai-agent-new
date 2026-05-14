"""Chart generation - matplotlib PNG charts for the report and the Analyst's vision input.

Saves PNGs to the working directory. Each function returns the file path.
"""
from __future__ import annotations
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # non-interactive backend for server use
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

from utils.ratios import RATIO_LABELS, PERCENT_RATIOS


# ----- Styling -----
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.titlesize": 13,
    "axes.titleweight": "bold",
    "axes.labelsize": 10,
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

PALETTE = ["#2E5994", "#E07A3F", "#3FA858", "#A33FA8", "#D4A93F",
           "#3FA8A8", "#A83F3F", "#5A5A5A"]


def _save(fig, out_dir: str, name: str, dpi: int = 130) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.png")
    fig.tight_layout()
    fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _is_pct(ratio_key: str) -> bool:
    return ratio_key in PERCENT_RATIOS


def _fmt_axis(ax, ratio_key: str):
    if _is_pct(ratio_key):
        ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=1))


# ===== Single-company trend chart (one ratio across years) =====
def trend_chart(ticker: str, ratios_by_year: dict, ratio_key: str,
                out_dir: str) -> str | None:
    """Line chart of one ratio over time for one company."""
    years = sorted(ratios_by_year.keys())
    values = [ratios_by_year[y].get(ratio_key) for y in years]
    if not any(v is not None for v in values):
        return None

    fig, ax = plt.subplots(figsize=(7, 4))
    valid_years = [y for y, v in zip(years, values) if v is not None]
    valid_values = [v for v in values if v is not None]

    ax.plot(valid_years, valid_values, marker="o", linewidth=2.2,
            color=PALETTE[0], markersize=7)
    ax.fill_between(valid_years, valid_values, alpha=0.15, color=PALETTE[0])

    ax.set_title(f"{ticker}: {RATIO_LABELS.get(ratio_key, ratio_key)} Trend")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel(RATIO_LABELS.get(ratio_key, ratio_key))
    _fmt_axis(ax, ratio_key)

    return _save(fig, out_dir, f"trend_{ticker}_{ratio_key}")


# ===== Profitability dashboard (multiple margin ratios on one chart) =====
def profitability_dashboard(ticker: str, ratios_by_year: dict, out_dir: str) -> str | None:
    keys = ["gross_margin", "operating_margin", "net_margin"]
    years = sorted(ratios_by_year.keys())
    if not years:
        return None

    fig, ax = plt.subplots(figsize=(8, 4.5))
    plotted = False
    for i, key in enumerate(keys):
        values = [ratios_by_year[y].get(key) for y in years]
        if not any(v is not None for v in values):
            continue
        valid_years = [y for y, v in zip(years, values) if v is not None]
        valid_values = [v for v in values if v is not None]
        ax.plot(valid_years, valid_values, marker="o", linewidth=2,
                label=RATIO_LABELS[key], color=PALETTE[i])
        plotted = True

    if not plotted:
        plt.close(fig)
        return None

    ax.set_title(f"{ticker}: Profitability Margins Over Time")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel("Margin")
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=1))
    ax.legend(loc="best", frameon=True)

    return _save(fig, out_dir, f"profitability_{ticker}")


# ===== DuPont decomposition chart =====
def dupont_chart(ticker: str, ratios_by_year: dict, out_dir: str) -> str | None:
    """Stacked bar showing the three DuPont drivers + ROE line."""
    years = sorted(ratios_by_year.keys())
    if not years:
        return None

    net_margins = []
    turnovers = []
    leverages = []
    roes = []
    valid_years = []
    for y in years:
        d = ratios_by_year[y].get("_dupont", {})
        nm = d.get("net_margin")
        at = d.get("asset_turnover")
        em = d.get("equity_multiplier")
        roe = d.get("roe_3step")
        if all(x is not None for x in [nm, at, em, roe]):
            net_margins.append(nm * 100)   # show as percentages
            turnovers.append(at)
            leverages.append(em)
            roes.append(roe * 100)
            valid_years.append(y)

    if not valid_years:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

    # Left: the three drivers (normalized for visual comparison)
    width = 0.25
    x = range(len(valid_years))
    ax1.bar([i - width for i in x], net_margins, width, label="Net Margin (%)",
            color=PALETTE[0])
    ax1.bar([i for i in x], turnovers, width, label="Asset Turnover (×)",
            color=PALETTE[1])
    ax1.bar([i + width for i in x], leverages, width, label="Equity Multiplier (×)",
            color=PALETTE[2])
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(valid_years)
    ax1.set_title(f"{ticker}: DuPont 3-Step Components")
    ax1.set_xlabel("Fiscal Year")
    ax1.legend(loc="best", fontsize=8)

    # Right: resulting ROE
    ax2.plot(valid_years, roes, marker="o", linewidth=2.4, color=PALETTE[3],
             markersize=8)
    ax2.fill_between(valid_years, roes, alpha=0.18, color=PALETTE[3])
    ax2.set_title(f"{ticker}: Resulting ROE (DuPont)")
    ax2.set_xlabel("Fiscal Year")
    ax2.set_ylabel("ROE (%)")
    ax2.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=100, decimals=1))

    return _save(fig, out_dir, f"dupont_{ticker}")


# ===== Peer comparison bar chart =====
def peer_comparison_chart(primary: str, peer_analysis_for_ratio: dict,
                          ratio_key: str, out_dir: str) -> str | None:
    """Horizontal bar comparing the primary company against its peer set on one ratio."""
    primary_value = peer_analysis_for_ratio.get("primary_value")
    peer_values = peer_analysis_for_ratio.get("peer_values", {})
    if primary_value is None or not peer_values:
        return None

    names = [primary] + list(peer_values.keys())
    values = [primary_value] + list(peer_values.values())
    # Filter out None peer values
    filtered = [(n, v) for n, v in zip(names, values) if v is not None]
    if len(filtered) < 2:
        return None
    names, values = zip(*filtered)

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = [PALETTE[0] if n == primary else "#B0B0B0" for n in names]
    bars = ax.barh(names, values, color=colors)
    ax.set_title(f"{primary}: {RATIO_LABELS.get(ratio_key, ratio_key)} vs Peers")
    ax.set_xlabel(RATIO_LABELS.get(ratio_key, ratio_key))
    if _is_pct(ratio_key):
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=1))

    # Label bars
    for bar, val in zip(bars, values):
        text = f"{val*100:.1f}%" if _is_pct(ratio_key) else f"{val:.2f}"
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                f"  {text}", va="center", fontsize=9)
    ax.invert_yaxis()  # primary on top

    return _save(fig, out_dir, f"peer_{primary}_{ratio_key}")


# ===== Multi-company comparison (when user asked for a comparison) =====
def multi_company_chart(tickers: list[str], ratios: dict,
                        ratio_key: str, out_dir: str) -> str | None:
    """Line chart of one ratio across years for multiple companies."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    plotted = False
    for i, ticker in enumerate(tickers):
        by_year = ratios.get(ticker, {})
        years = sorted(by_year.keys())
        values = [by_year[y].get(ratio_key) for y in years]
        if not any(v is not None for v in values):
            continue
        valid_years = [y for y, v in zip(years, values) if v is not None]
        valid_values = [v for v in values if v is not None]
        ax.plot(valid_years, valid_values, marker="o", linewidth=2,
                label=ticker, color=PALETTE[i % len(PALETTE)])
        plotted = True

    if not plotted:
        plt.close(fig)
        return None

    ax.set_title(f"{RATIO_LABELS.get(ratio_key, ratio_key)}: Multi-Company Comparison")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel(RATIO_LABELS.get(ratio_key, ratio_key))
    _fmt_axis(ax, ratio_key)
    ax.legend(loc="best")

    return _save(fig, out_dir, f"compare_{ratio_key}")


# ===== Win tally for head-to-head =====
def win_tally_chart(win_tally: dict, out_dir: str) -> str | None:
    if not win_tally:
        return None
    items = sorted(win_tally.items(), key=lambda x: -x[1])
    names = [n for n, _ in items]
    wins = [w for _, w in items]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    bars = ax.barh(names, wins, color=[PALETTE[i % len(PALETTE)] for i in range(len(names))])
    ax.set_title("Head-to-Head: Best-in-Class Wins per Company")
    ax.set_xlabel("Number of ratios where company ranks #1")
    for bar, w in zip(bars, wins):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                f"  {w}", va="center", fontsize=10, fontweight="bold")
    ax.invert_yaxis()

    return _save(fig, out_dir, "win_tally")
