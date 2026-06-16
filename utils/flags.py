"""Flags & Signals — a deterministic rule engine over the computed numbers.

Pure-Python, no LLM. Scans the ratios, trends, fundamentals and valuation and
emits structured, direction-aware signals classified as:

    positive  — a strength / green light
    watch     — something to keep an eye on / yellow light
    concern   — a genuine red flag

Each signal carries a category, a short title, and a detail string that cites
the specific numbers. A summary tallies the three buckets and states an overall
tilt. The Analyst then writes prose grounded in THESE signals rather than
inventing its own, so the "concerns" section is stable and accurate.
"""
from __future__ import annotations
from utils.ratios import PERCENT_RATIOS, RATIO_LABELS

HIGHER_BETTER = {"gross_margin", "operating_margin", "net_margin", "roa",
                 "current_ratio", "quick_ratio", "cash_ratio",
                 "interest_coverage", "asset_turnover", "fcf_margin",
                 "ocf_to_net_income"}
LOWER_BETTER = {"debt_to_equity", "debt_to_assets", "equity_multiplier"}


def _flag(sev, cat, title, detail):
    return {"severity": sev, "category": cat, "title": title, "detail": detail}


def _fv(key, v):
    if v is None:
        return "n/a"
    if key in PERCENT_RATIOS:
        return f"{v*100:.1f}%"
    return f"{v:.2f}"


def _pct(x):
    return "n/a" if x is None else f"{x*100:.1f}%"


def _money(v):
    if v is None:
        return "n/a"
    a = abs(v)
    if a >= 1e12:
        return f"${v/1e12:.2f}T"
    if a >= 1e9:
        return f"${v/1e9:.1f}B"
    if a >= 1e6:
        return f"${v/1e6:.1f}M"
    return f"${v:,.0f}"


def _years_sorted(by_year):
    def keyf(y):
        try:
            return int(y)
        except ValueError:
            return y
    return sorted(by_year.keys(), key=keyf)


def _cagr_of(trends, key):
    t = trends.get(key) if trends else None
    return t.get("cagr") if t else None


def compute_flags(by_year: dict, trends: dict, fundamentals: dict,
                  val_peers: dict) -> dict:
    """Return {positive: [...], watch: [...], concern: [...], summary: {...}}."""
    out = {"positive": [], "watch": [], "concern": []}

    def add(f):
        out[f["severity"]].append(f)

    years = _years_sorted(by_year)
    if not years:
        return {**out, "summary": {"positive": 0, "watch": 0, "concern": 0,
                                   "tilt": "No data", "line": "No ratios available."}}
    lv = by_year[years[-1]]
    dupont = lv.get("_dupont", {})
    fundamentals = fundamentals or {}
    growth = fundamentals.get("growth", {}) or {}
    valuation = fundamentals.get("valuation", {}) or {}
    capalloc = fundamentals.get("capital_allocation", {}) or {}
    val_peers = val_peers or {}

    # ---------------- Liquidity ----------------
    cr = lv.get("current_ratio")
    if cr is not None:
        if cr < 0.75:
            add(_flag("concern", "Liquidity", "Tight short-term liquidity",
                      f"Current ratio {cr:.2f} (<0.75): current liabilities materially "
                      f"exceed current assets."))
        elif cr < 1.0:
            add(_flag("watch", "Liquidity", "Current ratio below 1",
                      f"Current ratio {cr:.2f}: current liabilities exceed current "
                      f"assets — acceptable if operating cash flow is strong, otherwise "
                      f"a liquidity risk."))
        elif cr >= 1.5:
            add(_flag("positive", "Liquidity", "Comfortable liquidity",
                      f"Current ratio {cr:.2f} gives a solid short-term cushion."))

    # ---------------- Leverage / solvency ----------------
    ic = lv.get("interest_coverage")
    if ic is not None:
        if ic < 3:
            add(_flag("concern", "Solvency", "Thin interest coverage",
                      f"Interest coverage {ic:.1f}× (<3): limited buffer to service "
                      f"interest from operating profit."))
        elif ic < 6:
            add(_flag("watch", "Solvency", "Modest interest coverage",
                      f"Interest coverage {ic:.1f}×: adequate but not generous."))
        elif ic >= 12:
            add(_flag("positive", "Solvency", "Strong interest coverage",
                      f"Interest coverage {ic:.1f}× — interest is comfortably covered."))
    ic_cagr = _cagr_of(trends, "interest_coverage")
    if ic_cagr is not None and ic_cagr < -0.15:
        t = trends["interest_coverage"]
        add(_flag("watch", "Solvency", "Interest coverage declining",
                  f"Interest coverage fell from {_fv('interest_coverage', t.get('first_value'))} "
                  f"to {_fv('interest_coverage', t.get('last_value'))} "
                  f"(CAGR {_pct(ic_cagr)})."))

    de_cagr = _cagr_of(trends, "debt_to_equity")
    de = lv.get("debt_to_equity")
    if de_cagr is not None and de_cagr < -0.05:
        add(_flag("positive", "Leverage", "Deleveraging",
                  f"Debt/equity is falling (now {_fv('debt_to_equity', de)}, "
                  f"CAGR {_pct(de_cagr)}) — a more conservative balance sheet."))
    elif de_cagr is not None and de_cagr > 0.10 and (de or 0) > 1.5:
        add(_flag("watch", "Leverage", "Rising leverage",
                  f"Debt/equity is climbing (now {_fv('debt_to_equity', de)}, "
                  f"CAGR {_pct(de_cagr)})."))
    da = lv.get("debt_to_assets")
    if da is not None and da > 0.6:
        add(_flag("watch", "Leverage", "High debt load",
                  f"Debt/assets {da*100:.0f}% — a large share of assets is debt-funded."))

    # ---------------- Profitability & margins ----------------
    nm_cagr = _cagr_of(trends, "net_margin")
    if nm_cagr is not None:
        t = trends["net_margin"]
        if nm_cagr > 0.02:
            add(_flag("positive", "Profitability", "Margin expansion",
                      f"Net margin improving ({_fv('net_margin', t.get('first_value'))} → "
                      f"{_fv('net_margin', t.get('last_value'))}, CAGR {_pct(nm_cagr)})."))
        elif nm_cagr < -0.03:
            add(_flag("watch", "Profitability", "Margin compression",
                      f"Net margin slipping ({_fv('net_margin', t.get('first_value'))} → "
                      f"{_fv('net_margin', t.get('last_value'))}, CAGR {_pct(nm_cagr)})."))

    # ---------------- ROE quality (DuPont) ----------------
    em = dupont.get("equity_multiplier")
    if em is not None and em > 4:
        add(_flag("watch", "ROE quality", "Leverage-driven ROE",
                  f"ROE is amplified by high financial leverage (equity multiplier "
                  f"{em:.1f}×): a large part of ROE comes from leverage, not operations."))
    roe_cagr = _cagr_of(trends, "roe")
    em_cagr = _cagr_of(trends, "equity_multiplier")
    if (roe_cagr is not None and roe_cagr < -0.03 and (nm_cagr or 0) >= 0
            and em_cagr is not None and em_cagr < 0):
        add(_flag("positive", "ROE quality", "ROE decline is healthy deleveraging",
                  "ROE fell, but because leverage came down while margins held — "
                  "de-risking, not weaker operations."))

    # ---------------- Earnings quality / cash flow ----------------
    ocf_ni = lv.get("ocf_to_net_income")
    if ocf_ni is not None:
        if ocf_ni < 0.9:
            add(_flag("watch", "Earnings quality", "Earnings not fully cash-backed",
                      f"Operating cash flow is {ocf_ni:.2f}× net income (<1): reported "
                      f"profit is not fully converted to cash this year."))
        elif ocf_ni >= 1.1:
            add(_flag("positive", "Earnings quality", "High earnings quality",
                      f"Operating cash flow is {ocf_ni:.2f}× net income — earnings are "
                      f"well backed by cash."))
    fcf_m = lv.get("fcf_margin")
    if fcf_m is not None and fcf_m < 0:
        add(_flag("concern", "Cash flow", "Negative free cash flow",
                  f"Free-cash-flow margin {fcf_m*100:.1f}% — the business is consuming cash."))
    else:
        fcf_cagr = _cagr_of(trends, "fcf_margin")
        if fcf_cagr is not None and fcf_cagr < -0.05:
            add(_flag("watch", "Cash flow", "Free cash flow margin sliding",
                      f"FCF margin trending down (CAGR {_pct(fcf_cagr)})."))

    # ---------------- Growth ----------------
    rev = growth.get("revenue")
    if rev and rev.get("cagr") is not None:
        g = rev["cagr"]
        if g < 0:
            add(_flag("concern", "Growth", "Revenue declining",
                      f"Revenue shrank ({_money(rev.get('first'))} → {_money(rev.get('last'))}, "
                      f"CAGR {_pct(g)})."))
        elif g >= 0.10:
            add(_flag("positive", "Growth", "Strong revenue growth",
                      f"Revenue compounding at {_pct(g)} ({_money(rev.get('first'))} → "
                      f"{_money(rev.get('last'))})."))
    eps = growth.get("eps")
    if (eps and rev and eps.get("cagr") is not None and rev.get("cagr") is not None
            and eps["cagr"] > 0 and eps["cagr"] > rev["cagr"] + 0.02):
        add(_flag("positive", "Growth", "EPS outgrowing revenue",
                  f"EPS CAGR {_pct(eps['cagr'])} exceeds revenue CAGR {_pct(rev['cagr'])} — "
                  f"margin gains and/or buybacks are lifting per-share earnings."))
    ni = growth.get("net_income")
    if ni and ni.get("cagr") is not None and ni["cagr"] < 0:
        add(_flag("watch", "Growth", "Earnings shrinking",
                  f"Net income declining (CAGR {_pct(ni['cagr'])})."))

    # ---------------- Valuation vs peers ----------------
    pe = val_peers.get("pe")
    if pe and pe.get("company") is not None and pe.get("peer_median"):
        c, med = pe["company"], pe["peer_median"]
        if med > 0 and c > med * 1.3:
            add(_flag("watch", "Valuation", "Premium valuation vs peers",
                      f"P/E {c:.1f}× is well above the peer median {med:.1f}× — priced for "
                      f"more growth/quality than peers."))
        elif med > 0 and c < med * 0.7:
            add(_flag("positive", "Valuation", "Discount to peers",
                      f"P/E {c:.1f}× is below the peer median {med:.1f}×."))

    # ---------------- Capital allocation ----------------
    sy = capalloc.get("shareholder_yield")
    if sy is not None and sy > 0.03:
        add(_flag("positive", "Capital allocation", "Generous shareholder returns",
                  f"Returned {_money(capalloc.get('total_returned'))} to shareholders "
                  f"(~{sy*100:.1f}% of market cap) via buybacks and dividends."))
    tpr = capalloc.get("total_payout_ratio")
    if tpr is not None and tpr > 1.0:
        add(_flag("watch", "Capital allocation", "Paying out more than it earns",
                  f"Total payout (dividends + buybacks) is {tpr*100:.0f}% of net income — "
                  f"partly funded from the balance sheet rather than current profit."))

    # ---------------- Summary / overall tilt ----------------
    npos, nwatch, ncon = len(out["positive"]), len(out["watch"]), len(out["concern"])
    if ncon >= 2:
        tilt = "Cautious — multiple red flags"
    elif ncon == 1 and npos <= nwatch:
        tilt = "Mixed — a notable concern alongside some strengths"
    elif npos > nwatch + ncon:
        tilt = "Net positive — strengths outweigh the watch items"
    elif npos == 0 and nwatch == 0 and ncon == 0:
        tilt = "Neutral — no strong signals either way"
    else:
        tilt = "Balanced — strengths and watch items roughly offset"
    out["summary"] = {
        "positive": npos, "watch": nwatch, "concern": ncon, "tilt": tilt,
        "line": f"{npos} strength(s) · {nwatch} watch item(s) · {ncon} concern(s).",
    }
    return out
