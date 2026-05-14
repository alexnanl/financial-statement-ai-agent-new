"""Chart generation - matplotlib PNG charts for the report and the Analyst's vision input.

Saves PNGs to the working directory. Each function returns the file path.

v3 changes:
  - Chart sizes tuned to fit cleanly inside an A4/Letter report column
    (no oversized figures that overflow the page).
  - Consistent, lighter styling that matches the professional HTML template.
  - Higher DPI but smaller physical size => crisp but compact images.
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
    "figure.dpi": 100,
    "savefig.dpi": 150,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "axes.edgecolor": "#cccccc",
    "axes.titlecolor": "#1f4e79",
})

PALETTE = ["#1f4e79", "#c00000", "#2c5282", "#3FA858", "#D4A93F",
           "#A33FA8", "#3FA8A8", "#5A5A5A"]

# Report-appropriate figure sizes (inches). Kept small so they sit nicely
# inside the ~6.5in printable width of an A4/Letter page.
SIZE_SINGLE = (5.6, 3.1)      # one-panel line/bar chart
SIZE_WIDE = (6.4, 3.3)        # slightly wider single panel
SIZE_DUAL = (6.8, 3.0)        # two-panel (DuPont)
SIZE_BAR = (5.6, 2.9)         # horizontal bar charts


def _save(fig, out_dir: str, name: str) -> str:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(out_dir, f"{name}.png")
    fig.tight_layout(pad=0.6)
    fig.savefig(path, bbox_inches="tight", facecolor="white", pad_inches=0.08)
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

    fig, ax = plt.subplots(figsize=SIZE_SINGLE)
    valid_years = [y for y, v in zip(years, values) if v is not None]
    valid_values = [v for v in values if v is not None]

    ax.plot(valid_years, valid_values, marker="o", linewidth=2,
            color=PALETTE[0], markersize=5)
    ax.fill_between(valid_years, valid_values, alpha=0.12, color=PALETTE[0])

    ax.set_title(f"{ticker}: {RATIO_LABELS.get(ratio_key, ratio_key)} Trend")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel(RATIO_LABELS.get(ratio_key, ratio_key))
    ax.set_xticks(valid_years)
    _fmt_axis(ax, ratio_key)

    return _save(fig, out_dir, f"trend_{ticker}_{ratio_key}")


# ===== Profitability dashboard (multiple margin ratios on one chart) =====
def profitability_dashboard(ticker: str, ratios_by_year: dict, out_dir: str) -> str | None:
    keys = ["gross_margin", "operating_margin", "net_margin"]
    years = sorted(ratios_by_year.keys())
    if not years:
        return None

    fig, ax = plt.subplots(figsize=SIZE_WIDE)
    plotted = False
    for i, key in enumerate(keys):
        values = [ratios_by_year[y].get(key) for y in years]
        if not any(v is not None for v in values):
            continue
        valid_years = [y for y, v in zip(years, values) if v is not None]
        valid_values = [v for v in values if v is not None]
        ax.plot(valid_years, valid_values, marker="o", linewidth=2,
                label=RATIO_LABELS[key], color=PALETTE[i], markersize=5)
        plotted = True

    if not plotted:
        plt.close(fig)
        return None

    ax.set_title(f"{ticker}: Profitability Margins Over Time")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel("Margin")
    ax.set_xticks(sorted(years))
    ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=1))
    ax.legend(loc="best", frameon=True, framealpha=0.9)

    return _save(fig, out_dir, f"profitability_{ticker}")


# ===== DuPont decomposition chart =====
def dupont_chart(ticker: str, ratios_by_year: dict, out_dir: str) -> str | None:
    """Two-panel: the three DuPont drivers (bars) + resulting ROE (line)."""
    years = sorted(ratios_by_year.keys())
    if not years:
        return None

    net_margins, turnovers, leverages, roes, valid_years = [], [], [], [], []
    for y in years:
        d = ratios_by_year[y].get("_dupont", {})
        nm = d.get("net_margin")
        at = d.get("asset_turnover")
        em = d.get("equity_multiplier")
        roe = d.get("roe_3step")
        if all(x is not None for x in [nm, at, em, roe]):
            net_margins.append(nm * 100)
            turnovers.append(at)
            leverages.append(em)
            roes.append(roe * 100)
            valid_years.append(y)

    if not valid_years:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=SIZE_DUAL)

    width = 0.25
    x = range(len(valid_years))
    ax1.bar([i - width for i in x], net_margins, width, label="Net Margin (%)",
            color=PALETTE[0])
    ax1.bar([i for i in x], turnovers, width, label="Asset Turnover (×)",
            color=PALETTE[1])
    ax1.bar([i + width for i in x], leverages, width, label="Equity Mult. (×)",
            color=PALETTE[3])
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(valid_years)
    ax1.set_title(f"{ticker}: DuPont 3-Step Components")
    ax1.set_xlabel("Fiscal Year")
    ax1.legend(loc="best", fontsize=7)

    ax2.plot(valid_years, roes, marker="o", linewidth=2.2, color=PALETTE[1],
             markersize=6)
    ax2.fill_between(valid_years, roes, alpha=0.15, color=PALETTE[1])
    ax2.set_title(f"{ticker}: Resulting ROE")
    ax2.set_xlabel("Fiscal Year")
    ax2.set_ylabel("ROE (%)")
    ax2.set_xticks(valid_years)
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
    filtered = [(n, v) for n, v in zip(names, values) if v is not None]
    if len(filtered) < 2:
        return None
    names, values = zip(*filtered)

    fig, ax = plt.subplots(figsize=SIZE_BAR)
    colors = [PALETTE[0] if n == primary else "#b9c2cc" for n in names]
    bars = ax.barh(names, values, color=colors, height=0.6)
    ax.set_title(f"{primary}: {RATIO_LABELS.get(ratio_key, ratio_key)} vs Peers")
    ax.set_xlabel(RATIO_LABELS.get(ratio_key, ratio_key))
    if _is_pct(ratio_key):
        ax.xaxis.set_major_formatter(mtick.PercentFormatter(xmax=1.0, decimals=1))

    for bar, val in zip(bars, values):
        text = f"{val*100:.1f}%" if _is_pct(ratio_key) else f"{val:.2f}"
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                f"  {text}", va="center", fontsize=8)
    ax.invert_yaxis()
    ax.margins(x=0.15)

    return _save(fig, out_dir, f"peer_{primary}_{ratio_key}")


# ===== Multi-company comparison (when user asked for a comparison) =====
def multi_company_chart(tickers: list[str], ratios: dict,
                        ratio_key: str, out_dir: str) -> str | None:
    """Line chart of one ratio across years for multiple companies."""
    fig, ax = plt.subplots(figsize=SIZE_WIDE)
    plotted = False
    all_years: set = set()
    for i, ticker in enumerate(tickers):
        by_year = ratios.get(ticker, {})
        years = sorted(by_year.keys())
        values = [by_year[y].get(ratio_key) for y in years]
        if not any(v is not None for v in values):
            continue
        valid_years = [y for y, v in zip(years, values) if v is not None]
        valid_values = [v for v in values if v is not None]
        all_years.update(valid_years)
        ax.plot(valid_years, valid_values, marker="o", linewidth=2,
                label=ticker, color=PALETTE[i % len(PALETTE)], markersize=5)
        plotted = True

    if not plotted:
        plt.close(fig)
        return None

    ax.set_title(f"{RATIO_LABELS.get(ratio_key, ratio_key)}: Multi-Company Comparison")
    ax.set_xlabel("Fiscal Year")
    ax.set_ylabel(RATIO_LABELS.get(ratio_key, ratio_key))
    if all_years:
        ax.set_xticks(sorted(all_years))
    _fmt_axis(ax, ratio_key)
    ax.legend(loc="best", framealpha=0.9)

    return _save(fig, out_dir, f"compare_{ratio_key}")


# ===== Win tally for head-to-head =====
def win_tally_chart(win_tally: dict, out_dir: str) -> str | None:
    if not win_tally:
        return None
    items = sorted(win_tally.items(), key=lambda x: -x[1])
    names = [n for n, _ in items]
    wins = [w for _, w in items]

    fig, ax = plt.subplots(figsize=SIZE_BAR)
    bars = ax.barh(names, wins, height=0.6,
                   color=[PALETTE[i % len(PALETTE)] for i in range(len(names))])
    ax.set_title("Head-to-Head: Best-in-Class Wins per Company")
    ax.set_xlabel("Number of ratios ranked #1")
    for bar, w in zip(bars, wins):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height()/2,
                f"  {w}", va="center", fontsize=9, fontweight="bold")
    ax.invert_yaxis()
    ax.margins(x=0.12)

    return _save(fig, out_dir, "win_tally")
