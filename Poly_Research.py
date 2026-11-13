"""
Polygon Conjoinability Research - Streamlit Dashboard
Muhammad Zaid Bilal | May 2026

Requirements (Python 3.10+):
  pip install streamlit pandas numpy matplotlib seaborn plotly openpyxl shapely

Keep Polygon_solver.py and Polygon_placements.py in the same folder (they power the "Geometric Solver"
and "Placements" tabs).

Run:
  streamlit run Poly_Research.py

Place spreadsheet_kn_corrected_final.xlsx (or the corrected CSV) in the same folder, or upload it via the sidebar.
"""

# ---------------------------------------------------------------------------
# IMPORTS
# ---------------------------------------------------------------------------
import io
import math
import warnings
import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.colors as mcolors
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

warnings.filterwarnings("ignore")

import importlib

ps, SOLVER_OK, _solver_errs = None, False, []
for _mod in ("Polygon_solver", "polygon_solver"):      # exact geometric solver (needs shapely)
    try:
        ps = importlib.import_module(_mod)
        SOLVER_OK = True
        break
    except ModuleNotFoundError as _exc:
        # a missing dependency (e.g. shapely) is more informative than a missing module file
        (_solver_errs.append if _exc.name == _mod else lambda m: _solver_errs.insert(0, m))(str(_exc))
    except Exception as _exc:
        _solver_errs.insert(0, str(_exc))
SOLVER_ERR = "" if SOLVER_OK else (_solver_errs[0] if _solver_errs else "unknown error")

pl, PLACEMENTS_OK, _pl_errs = None, False, []
for _mod in ("Polygon_placements", "polygon_placements"):   # all valid placements (needs Polygon_solver)
    try:
        pl = importlib.import_module(_mod)
        PLACEMENTS_OK = True
        break
    except ModuleNotFoundError as _exc:
        (_pl_errs.append if _exc.name == _mod else lambda m: _pl_errs.insert(0, m))(str(_exc))
    except Exception as _exc:
        _pl_errs.insert(0, str(_exc))
PLACEMENTS_ERR = "" if PLACEMENTS_OK else (_pl_errs[0] if _pl_errs else "unknown error")

# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Polygon Conjoinability Research",
    page_icon="HEX",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# COLOUR PALETTE  (shared by matplotlib + plotly)
# ---------------------------------------------------------------------------
C = {
    "k6"       : "#2EA84C",   # green   - k=6 Hexagonal Resonance
    "mt"       : "#D63B3B",   # red     - Maximally Tense
    "mp"       : "#E07B20",   # orange  - Multiple Placements
    "ps"       : "#7B3FA0",   # purple  - Phase Shift
    "k_line"   : "#2B6CB0",   # blue    - k(n) default line
    "s_line"   : "#C05621",   # burnt   - s(n) default line
    "approx"   : "#888888",   # grey    - simple formula
    "refined"  : "#CC5500",   # dark-o  - refined formula
    "other"    : "#6B7280",   # slate   - unmapped states
    "bg"       : "#F8F9FB",
    "grid"     : "#DDE3EE",
}

TENSION_CMAP = {
    "minimally tense"                               : "#68D391",
    "maximally tense"                               : C["mt"],
    "maximally tense (hexagonal resonance)"         : C["k6"],
    "maximally tense, symmetric"                    : C["k6"],
    "maximally tense, symmetric "                   : C["k6"],
    "hexagonal resonance"                           : C["k6"],
    "hexagonal resonance "                          : C["k6"],
    "phase shift"                                   : C["ps"],
    "multiple placements (2)"                       : C["mp"],
    "multiple placements(2)"                        : C["mp"],
    "multiple placement (2)"                        : C["mp"],
    "minimally tense, multiple placements (2)"      : "#DD6B20",
    "0"                                             : C["k_line"],
    ""                                              : C["k_line"],
    "normal"                                        : C["k_line"],
}

def tension_color(state: str) -> str:
    return TENSION_CMAP.get(str(state).strip().lower(), C["other"])

# ---------------------------------------------------------------------------
# FORMULA HELPERS
# ---------------------------------------------------------------------------
def s_exact(n: int) -> int:
    """Exact: s(n) = max(0, ceil(n/6) - 2) -- untouched vertices of the central polygon
    between two adjacent neighbours at the smallest non-overlapping edge spacing ceil(n/6)."""
    return max(0, math.ceil(n / 6) - 2)

def k_exact(n: int) -> int:
    """Exact: k(n) = n for n <= 6, otherwise floor(n / ceil(n/6))."""
    return n if n <= 6 else n // math.ceil(n / 6)

def s_simple(n: int) -> int:
    """Superseded approximation max(0, floor((n-6)/6)). Right at non-multiples of 6,
    one too high at multiples of 6. Kept only for comparison."""
    return max(0, int((n - 6) // 6))

# ---------------------------------------------------------------------------
# SHEET DETECTION & PARSING  (handles every sheet type in the workbook)
# ---------------------------------------------------------------------------
MAIN_COL_ALIASES = {
    "vertices"                          : "n",
    "k(n) conjoinability"               : "k_n",
    "vertex skipping"                   : "vertex_skipping",
    "number of vertex skipped"          : "s_n",
    "internal angle of regular polygon" : "angle_str",
    "tension state"                     : "tension_state",
}
ANGLE_SHEET_ALIASES = {
    "number of vertex skipped" : "s_n",
    "angle degrees"            : "angle_deg",
    "internal angle (radians)" : "angle_rad",
}
HR_SHEET_ALIASES = {
    "side"                                                         : "n",
    "interior angle"                                               : "int_angle_deg",
    "exterior angle"                                               : "ext_angle_deg",
    "ratio of exterior angles over previous multiple of 6"        : "ext_ratio",
}

def _norm_cols(df: pd.DataFrame, alias_map: dict) -> pd.DataFrame:
    df.columns = [str(c).strip() for c in df.columns]
    rename = {c: alias_map[c.lower()] for c in df.columns if c.lower() in alias_map}
    return df.rename(columns=rename)

def classify_sheet(raw: pd.DataFrame) -> str:
    """Return one of: 'main', 'hr_angles', 'chart_deg', 'chart_rad', 'empty', 'unknown'"""
    cols_lower = [str(c).strip().lower() for c in raw.columns]
    joined = " | ".join(cols_lower)
    if "n" in cols_lower and "k_n" in cols_lower:      # cleaned CSV schema
        return "main"
    if "vertices" in joined and "k(n)" in joined:
        return "main"
    if "side" in joined and "exterior angle" in joined:
        return "hr_angles"
    # chart sheets have unnamed cols; peek at row-1 header
    if "unnamed: 0" in cols_lower:
        peek = str(raw.iloc[0, 0]).strip().lower() if len(raw) > 0 else ""
        peek1 = str(raw.iloc[0, 1]).strip().lower() if len(raw) > 0 and raw.shape[1] > 1 else ""
        if "angle degrees" in peek1 or "angle degrees" in peek:
            return "chart_deg"
        if "radians" in peek1 or "radians" in peek:
            return "chart_rad"
    if raw.empty or raw.shape[0] == 0:
        return "empty"
    return "unknown"

def parse_main_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    df = _norm_cols(raw.copy(), MAIN_COL_ALIASES)
    # Drop junk unnamed cols
    df = df[[c for c in df.columns if not str(c).startswith("Unnamed")]]
    n_raw = pd.to_numeric(df.get("n", pd.Series(dtype=float)), errors="coerce")
    df["k_n"] = pd.to_numeric(df.get("k_n", pd.Series(dtype=float)), errors="coerce")
    # Column A holds "=A57+1"-style formulas. If the workbook was re-saved by a tool that drops cached
    # formula results, those cells read as NaN although k(n) is present: rebuild n by counting rows.
    n_missing = n_raw.isna() & df["k_n"].notna()
    n_rebuilt = 0
    if n_missing.any() and n_raw.notna().any():
        pos = pd.Series(np.arange(len(n_raw)), index=n_raw.index)
        last_pos = pos.where(n_raw.notna()).ffill()
        n_filled = n_raw.ffill() + (pos - last_pos)
        n_raw = n_raw.where(~n_missing, n_filled)
        n_rebuilt = int(n_missing.sum())
    df["n"] = n_raw
    df["s_n"] = pd.to_numeric(df.get("s_n", pd.Series(dtype=float)), errors="coerce").fillna(0)
    df.dropna(subset=["n", "k_n"], inplace=True)
    df = df.drop_duplicates(subset=["n"], keep="first")
    df["n"]   = df["n"].astype(int)
    df["k_n"] = df["k_n"].astype(int)
    df["s_n"] = df["s_n"].astype(int)

    # Derived numeric columns
    df["angle_rad"] = (df["n"] - 2) * math.pi / df["n"]
    df["angle_deg"] = (df["n"] - 2) * 180.0 / df["n"]

    # Normalise tension_state strings ("Not assessed" marks rows with no tension analysis yet)
    if "tension_state" not in df.columns:
        df["tension_state"] = "Normal"
    df["tension_state"] = (
        df["tension_state"].fillna("Normal").astype(str)
        .replace({"0": "Normal", "0.0": "Normal", "nan": "Normal"})
        .str.strip()
    )

    ts = df["tension_state"].str.lower()
    df["assessed"]               = ts != "not assessed"
    df["is_hex_resonance"]       = (df["n"] % 6 == 0) & (df["k_n"] == 6)
    df["is_max_tense"]           = ts.str.contains("maximally tense", na=False)
    df["is_phase_shift"]         = ts.str.contains("phase shift", na=False)
    df["is_multiple_placements"] = ts.str.contains("multiple placement", na=False)
    df["is_minimally_tense"]     = ts.str.contains("minimally tense", na=False)
    df["uses_skipping"]          = df["s_n"] > 0

    # Plot colour per row
    df["plot_color"] = df["tension_state"].apply(tension_color)

    # Closed-form model columns (used to validate the data)
    df["s_exact"]  = df["n"].apply(s_exact)
    df["k_exact"]  = df["n"].apply(k_exact)
    df["s_simple"] = df["n"].apply(s_simple)

    df["hover"] = df.apply(
        lambda r: (f"n = {r['n']}<br>k(n) = {r['k_n']}<br>s(n) = {r['s_n']}<br>"
                   f"alpha = {r['angle_deg']:.2f} deg<br>Tension: {r['tension_state']}"),
        axis=1,
    )
    out = df.sort_values("n").reset_index(drop=True)
    out.attrs["n_rebuilt"] = n_rebuilt
    return out

def parse_hr_sheet(raw: pd.DataFrame) -> pd.DataFrame:
    df = _norm_cols(raw.copy(), HR_SHEET_ALIASES)
    for col in ["n", "int_angle_deg", "ext_angle_deg", "ext_ratio"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df.dropna(subset=["n"], inplace=True)
    df["n"] = df["n"].astype(int)
    return df.reset_index(drop=True)

def parse_chart_sheet(raw: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Parse the two chart sheets (skip the first two rows which are header-ish)."""
    df = raw.iloc[1:].copy()
    df.columns = [str(c).strip() for c in df.columns]
    if kind == "chart_deg":
        df.columns = ["s_n", "angle_deg"]
    else:
        df.columns = ["s_n", "angle_rad"]
    df = df.apply(pd.to_numeric, errors="coerce").dropna()
    df["s_n"] = df["s_n"].astype(int)
    return df.reset_index(drop=True)

# ---------------------------------------------------------------------------
# EDA HELPERS
# ---------------------------------------------------------------------------
def compute_eda(df: pd.DataFrame) -> dict:
    out = {}
    a = df[df["assessed"]]
    out["n_rows"]     = len(df)
    out["n_assessed"] = len(a)
    out["n_range"]    = (int(df["n"].min()), int(df["n"].max()))
    out["k_dist"]     = df["k_n"].value_counts().sort_index().to_dict()
    out["hr_ns"]      = sorted(df[df["is_hex_resonance"]]["n"].tolist())
    big = df[df["n"] >= 6]
    out["hr_law_holds"] = bool((((big["n"] % 6 == 0) == (big["k_n"] == 6))).all())
    out["mt_ns"]      = sorted(a[a["is_max_tense"] & ~a["is_hex_resonance"]]["n"].tolist())
    out["mp_ns"]      = sorted(df[df["is_multiple_placements"]]["n"].tolist())
    out["first_mp"]   = int(df[df["is_multiple_placements"]]["n"].min()) if out["mp_ns"] else None
    out["first_skip"] = int(df[df["uses_skipping"]]["n"].min()) if df["uses_skipping"].any() else None
    out["s_max"]      = int(df["s_n"].max())
    out["s_max_first_n"] = int(df.loc[df["s_n"].idxmax(), "n"])
    out["s_monotone"] = bool(df.sort_values("n")["s_n"].is_monotonic_increasing)
    out["tension_dist"] = df["tension_state"].value_counts().to_dict()
    out["pct_k6"] = round(100 * df["is_hex_resonance"].mean(), 1)
    out["pct_k5"] = round(100 * (df["k_n"] == 5).mean(), 1)
    out["pct_k4"] = round(100 * (df["k_n"] == 4).mean(), 1)
    out["corr_n_k"] = round(float(df[["n", "k_n"]].corr().iloc[0, 1]), 4)
    out["corr_n_s"] = round(float(df[["n", "s_n"]].corr().iloc[0, 1]), 4)

    # formula accuracy / data validation
    err_old = (df["s_n"] - df["s_simple"]).abs()
    err_s   = (df["s_n"] - df["s_exact"]).abs()
    err_k   = (df["k_n"] - df["k_exact"]).abs()
    out["simple_mae"]       = round(float(err_old.mean()), 4)
    out["simple_exact_pct"] = round(100 * (err_old == 0).mean(), 1)
    out["exact_mae"]        = round(float(err_s.mean()), 4)
    out["exact_pct"]        = round(100 * (err_s == 0).mean(), 1)
    out["k_exact_pct"]      = round(100 * (err_k == 0).mean(), 1)
    out["bad_s_ns"] = sorted(df[err_s != 0]["n"].tolist())
    out["bad_k_ns"] = sorted(df[err_k != 0]["n"].tolist())

    # Tension labels versus k = 6 (assessed rows only). The label is not used as evidence for H4.
    out["mt_all"]    = sorted(a[a["is_max_tense"]]["n"].tolist())
    out["hr_not_mt"] = sorted(a[a["is_hex_resonance"] & ~a["is_max_tense"]]["n"].tolist())
    return out

def generate_insights(df: pd.DataFrame, eda: dict) -> list[tuple[str, str]]:
    """Return list of (marker, insight_text) tuples."""
    ins = []
    hi = eda["n_range"][1]
    ins.append(("HEX", f"Hexagonal resonance of the conjoinability k(n): k(n) = 6 iff 6 divides n - "
                       f"{'holds' if eda['hr_law_holds'] else 'FAILS'} on every row from n = 6 to {hi} "
                       f"({len(eda['hr_ns'])} multiples of 6). It follows from k(n) = floor(n / ceil(n/6))."))
    k3 = sorted(df[(df["k_n"] == 3) & (df["n"] >= 7)]["n"].tolist())
    k4 = sorted(df[(df["k_n"] == 4) & (df["n"] >= 7)]["n"].tolist())
    ins.append(("NOTE", f"For n >= 7: k(n) = 3 at n in {k3}, k(n) = 4 at n in {k4}, and k(n) = 5 at every other "
                        f"non-multiple of 6 - in particular for all non-multiples of 6 from n = 20 upward."))
    ins.append(("DATA", f"Dataset spans n = {eda['n_range'][0]} to {hi} ({eda['n_rows']} rows, "
                        f"{eda['n_assessed']} with tension labels). k=6: {eda['pct_k6']}%, k=5: {eda['pct_k5']}%, k=4: {eda['pct_k4']}%."))
    bad = sorted(set(eda["bad_s_ns"]) | set(eda["bad_k_ns"]))
    ins.append(("MODEL", "Neighbours are full-edge reflections of the central polygon; the smallest non-overlapping edge "
                         "spacing is ceil(n/6), so k(n) = floor(n/ceil(n/6)) and s(n) = max(0, ceil(n/6) - 2). "
                         + (f"Data agrees with both formulas on every row." if not bad
                            else f"Rows that DISAGREE with the model: n in {bad}.")))
    ins.append(("STEP", "s(n) is monotone non-decreasing on this dataset - there is no step-back."
                        if eda["s_monotone"] else
                        "s(n) is NOT monotone on this dataset - check the rows flagged in the EDA tab."))
    ins.append(("SKIP", f"Vertex skipping first required at n = {eda['first_skip']} (s = 1). Maximum s(n) observed: "
                        f"s = {eda['s_max']}, first reached at n = {eda['s_max_first_n']}."))
    if eda["first_mp"]:
        ins.append(("ISOMER", f"'Multiple Placements (N)' labels are set for n = {eda['mp_ns'][0]}..{eda['mp_ns'][-1]} and N is the number "
                              f"of tight chains with BA fixed (3 for five neighbours). Such chains exist at every n with slack, from n = 7, "
                              f"so the labels do not mark a threshold; rows outside this range are simply not labelled."))
    ins.append(("CORR", f"Pearson correlation n<->k(n) = {eda['corr_n_k']} (near zero - k oscillates). "
                        f"Pearson correlation n<->s(n) = {eda['corr_n_s']} (strong positive - s grows with n)."))
    ins.append(("FORMULA", f"Exact formula max(0, ceil(n/6)-2): MAE = {eda['exact_mae']}, exact on {eda['exact_pct']}% of rows. "
                           f"The old approximation floor((n-6)/6): MAE = {eda['simple_mae']}, exact on {eda['simple_exact_pct']}% "
                           f"- right at non-multiples of 6, one too high at multiples of 6."))
    ins.append(("TENSE", f"Hand labels: 'Maximally Tense' at n in {eda['mt_all']}; k = 6 without that label at n in {eda['hr_not_mt']}. "
                         "The labels are not a function of k. Proved replacement (report Thm 7.1): the tension tau(n) between "
                         "adjacent tight neighbours is 0 iff 6 divides n iff k(n) = 6 (see Plot 10)."))
    return ins

# ---------------------------------------------------------------------------
# MATPLOTLIB PLOT FACTORIES  (each returns a plt.Figure)
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "figure.facecolor" : C["bg"],
    "axes.facecolor"   : C["bg"],
    "axes.edgecolor"   : "#CCCCCC",
    "axes.grid"        : True,
    "grid.color"       : C["grid"],
    "grid.linewidth"   : 0.7,
    "grid.alpha"       : 0.8,
    "font.size"        : 11,
    "axes.titlesize"   : 13,
    "axes.labelsize"   : 11,
})

def _label_ok(n) -> bool:
    """Only label a sparse subset of points so dense plots (n up to 400) stay readable."""
    return n <= 60 or n % 60 == 0 or n == 174

def _add_hr_vlines(ax, df):
    for n in df[df["is_hex_resonance"]]["n"]:
        ax.axvline(n, color=C["k6"], ls="--", lw=0.7, alpha=0.30)

# -- Plot 1: k(n) vs n ------------------------------------------------------
def fig_k_vs_n(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(13, 6))
    ax.plot(df["n"], df["k_n"], color=C["k_line"], lw=1.8, marker="o",
            ms=4, alpha=0.55, zorder=2)

    for _, row in df.iterrows():
        ax.scatter(row["n"], row["k_n"], color=row["plot_color"],
                   s=80, zorder=4, edgecolors="white", lw=0.4)

    _add_hr_vlines(ax, df)
    ax.axhline(6, color=C["k6"], lw=1.2, ls="--", alpha=0.55)
    ax.axhspan(5.88, 6.12, color=C["k6"], alpha=0.06)

    k6 = df[df["is_hex_resonance"]]
    ax.scatter(k6["n"], k6["k_n"], s=200, color=C["k6"], zorder=6,
               edgecolors="white", lw=0.8, label="Hexagonal Resonance (k=6)")
    for _, r in k6[k6["n"].apply(_label_ok)].iterrows():
        ax.text(r["n"], r["k_n"] + 0.22, f"n={r['n']}", color=C["k6"],
                fontsize=7.5, ha="center", fontweight="bold")

    mt = df[df["is_max_tense"] & ~df["is_hex_resonance"]]
    ax.scatter(mt["n"], mt["k_n"], s=130, color=C["mt"], marker="X",
               zorder=5, edgecolors="black", lw=0.4, label="Maximally Tense")
    for _, r in mt.iterrows():
        ax.text(r["n"], r["k_n"] - 0.30, f"MT {r['n']}", color=C["mt"],
                fontsize=7, ha="center")

    mp = df[df["is_multiple_placements"] & ~df["is_hex_resonance"]]
    ax.scatter(mp["n"], mp["k_n"], s=70, color=C["mp"], marker="D",
               zorder=3, alpha=0.75, label="Multiple Placements")

    ax.set_title("k(n) Conjoinability vs. n - Hexagonal Resonance at Multiples of 6",
                 fontweight="bold", pad=12)
    ax.set_xlabel("n (Number of Vertices)", fontweight="bold")
    ax.set_ylabel("k(n) Conjoinability", fontweight="bold")
    ax.set_yticks([3, 4, 5, 6]); ax.set_ylim(2.3, 7.2)
    ax.legend(fontsize=9, loc="lower right")
    fig.tight_layout()
    return fig

# -- Plot 2: s(n) vs n ------------------------------------------------------
def fig_s_vs_n(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(13, 6))

    ax.step(df["n"], df["s_n"], where="mid", color=C["s_line"],
            lw=1.8, ls="--", marker="o", ms=3, label="Data s(n)", zorder=3)

    n_cont = np.arange(df["n"].min(), df["n"].max() + 2)
    ax.plot(n_cont, [s_exact(n) for n in n_cont], color=C["refined"],
            lw=1.3, ls="-", label="Exact: max(0, ceil(n/6) - 2)", zorder=2)
    ax.plot(n_cont, [s_simple(n) for n in n_cont], color=C["approx"],
            lw=1.3, ls=":", label="Old approx: max(0, floor((n-6)/6))", zorder=1)

    k6 = df[df["is_hex_resonance"]]
    ax.scatter(k6["n"], k6["s_n"], s=110, color=C["k6"], marker="*",
               zorder=6, edgecolors="white", lw=0.6,
               label="s(n) at Hexagonal Resonance")
    for _, r in k6[k6["n"].apply(_label_ok)].iterrows():
        ax.text(r["n"], r["s_n"] + 0.25, f"n={r['n']},s={r['s_n']}",
                color=C["k6"], fontsize=7, ha="center", fontweight="bold")

    mt = df[df["is_max_tense"] & ~df["is_hex_resonance"]]
    ax.scatter(mt["n"], mt["s_n"], s=100, color=C["mt"], marker="X",
               zorder=5, edgecolors="black", lw=0.4, label="Maximally Tense")

    ax.set_title("s(n) Vertex Skipping vs. n - monotone, matches max(0, ceil(n/6) - 2)",
                 fontweight="bold", pad=12)
    ax.set_xlabel("n (Number of Vertices)", fontweight="bold")
    ax.set_ylabel("s(n) (Untouched vertices between neighbours)", fontweight="bold")
    ax.set_ylim(-0.5, df["s_n"].max() + 3)
    ax.legend(fontsize=8.5, loc="upper left")
    fig.tight_layout()
    return fig

# -- Plot 3: Dual-axis k(n) & s(n) ------------------------------------------
def fig_dual_axis(df: pd.DataFrame) -> plt.Figure:
    fig, ax1 = plt.subplots(figsize=(14, 6))
    ax2 = ax1.twinx()

    ax1.plot(df["n"], df["k_n"], color=C["k_line"], lw=1.8, marker="o",
             ms=4, label="k(n) Conjoinability", zorder=2)
    ax1.set_ylabel("k(n) Conjoinability", color=C["k_line"], fontweight="bold")
    ax1.set_yticks([3, 4, 5, 6]); ax1.set_ylim(2.0, 8.2)
    ax1.tick_params(axis="y", labelcolor=C["k_line"])

    ax2.step(df["n"], df["s_n"], where="mid", color=C["s_line"], lw=1.8,
             ls="--", marker="s", ms=3, label="s(n) Vertex Skipped", zorder=2)
    ax2.set_ylabel("s(n) Vertices Skipped", color=C["s_line"], fontweight="bold")
    ax2.set_ylim(-1, df["s_n"].max() + 4)
    ax2.tick_params(axis="y", labelcolor=C["s_line"])

    k6 = df[df["is_hex_resonance"]]
    ax1.scatter(k6["n"], k6["k_n"], s=180, color=C["k6"], zorder=6,
                edgecolors="white", lw=0.8, label="k(n) at HR")
    ax2.scatter(k6["n"], k6["s_n"], s=180, color=C["k6"], zorder=6,
                edgecolors="white", lw=0.8, label="s(n) at HR")
    for _, r in k6.iterrows():
        ax1.axvline(r["n"], color=C["k6"], ls="--", lw=0.6, alpha=0.28)
        if _label_ok(r["n"]):
            ax1.text(r["n"] + 0.4, r["k_n"] + 0.28,
                     f"n={r['n']},s={r['s_n']}", color=C["k6"],
                     fontsize=7.5, ha="left", fontweight="bold")

    mt = df[df["is_max_tense"] & ~df["is_hex_resonance"]]
    ax1.scatter(mt["n"], mt["k_n"], s=120, color=C["mt"], marker="X",
                zorder=5, edgecolors="black", lw=0.4, label="k(n) MT")
    ax2.scatter(mt["n"], mt["s_n"], s=120, color=C["mt"], marker="X", zorder=5)
    for _, r in mt.iterrows():
        ax1.text(r["n"] - 0.5, r["k_n"] - 0.32,
                 f"n={r['n']}", color=C["mt"], fontsize=7.5, ha="right")

    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper left", fontsize=8)
    ax1.set_xlabel("n (Number of Vertices)", fontweight="bold")
    fig.suptitle("Dual-Axis: k(n) Conjoinability & s(n) Vertex Skipping vs. n",
                 fontweight="bold", fontsize=13)
    fig.tight_layout()
    return fig

# -- Plot 4: Heatmap --------------------------------------------------------
def fig_heatmap(df: pd.DataFrame) -> plt.Figure:
    heat = df[["n", "k_n", "s_n"]].set_index("n").T
    dense = len(df) > 90
    width = min(40, max(16, len(df) * 0.42))
    fig, ax = plt.subplots(figsize=(width, 3.8))
    sns.heatmap(heat, annot=not dense, cmap="YlGnBu", fmt="d",
                linewidths=0 if dense else 0.35, linecolor="#CCCCCC",
                cbar_kws={"label": "Value", "shrink": 0.7}, ax=ax)
    ax.set_title("Heatmap: k(n) & s(n) vs. n", fontweight="bold", pad=10)
    ax.set_xlabel("n (Number of Vertices)", fontweight="bold")
    ax.set_yticklabels(["k(n)", "s(n)"], rotation=0)
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    fig.tight_layout()
    return fig

# -- Plot 5: s(n) vs k(n) ---------------------------------------------------
def fig_s_vs_k(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(13, 8))
    rng = np.random.default_rng(42)
    seen = set()
    for _, row in df.iterrows():
        st_ = str(row["tension_state"]).strip()
        col = tension_color(st_)
        lbl = st_ if st_ not in seen else "_nolegend_"
        seen.add(st_)
        jitter = rng.uniform(-0.06, 0.06)
        ax.scatter(row["s_n"] + jitter, row["k_n"] + rng.uniform(-0.04, 0.04),
                   color=col, s=70, alpha=0.80, edgecolors="black",
                   lw=0.3, label=lbl, zorder=4)
        if _label_ok(row["n"]):
            ax.text(row["s_n"] + jitter + 0.10, row["k_n"] + 0.05,
                    f"n={row['n']}", fontsize=6.5, alpha=0.82)

    ax.set_title("s(n) vs. k(n) - Annotated by n & Tension State",
                 fontweight="bold", pad=12)
    ax.set_xlabel("s(n) (Vertices Skipped)", fontweight="bold")
    ax.set_ylabel("k(n) (Conjoinability)", fontweight="bold")
    s_hi = int(df["s_n"].max())
    ax.set_xticks(range(int(df["s_n"].min()), s_hi + 1, max(1, s_hi // 25)))
    ax.set_yticks(range(int(df["k_n"].min()), int(df["k_n"].max()) + 1))
    ax.legend(title="Tension State", bbox_to_anchor=(1.02, 1),
              loc="upper left", fontsize=7, title_fontsize=9)
    fig.tight_layout()
    return fig

# -- Plot 6: Isomer Emergence ----------------------------------------------
def fig_isomer_emergence(df: pd.DataFrame) -> plt.Figure:
    df = df[df["assessed"]]          # isomer labels exist only for assessed rows
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    fig.suptitle("Rows Labelled Multiple Placements vs. n",
                 fontsize=13, fontweight="bold")

    iso = df["is_multiple_placements"].astype(int)
    axes[0].bar(df["n"], iso,
                color=[C["mp"] if v else "#B8C3D6" for v in iso],
                width=0.8, alpha=0.9)
    first_mp = df[df["is_multiple_placements"]]["n"].min() if iso.any() else None
    if first_mp:
        axes[0].axvline(first_mp, color="orange", lw=1.8, ls="--",
                        label=f"First labelled at n={first_mp}")
        for n_val in df[df["is_multiple_placements"]]["n"]:
            axes[0].text(n_val, 1.05, str(n_val), ha="center",
                         fontsize=6.5, color=C["mp"], rotation=90)
    axes[0].set_yticks([0, 1]); axes[0].set_yticklabels(["No", "Yes"])
    axes[0].set_ylabel("Multiple Placements?", fontweight="bold")
    axes[0].legend(fontsize=9)
    axes[0].set_title("Rows labelled Multiple Placements", fontsize=11)

    col2 = [C["k6"] if r["is_hex_resonance"]
             else C["mt"] if r["is_max_tense"]
             else C["mp"] if r["is_multiple_placements"]
             else C["k_line"]
             for _, r in df.iterrows()]
    axes[1].scatter(df["n"], df["k_n"], c=col2, s=90, zorder=5,
                    edgecolors="white", lw=0.5)
    axes[1].plot(df["n"], df["k_n"], color=C["k_line"], alpha=0.25, lw=1.2)
    if first_mp:
        axes[1].axvspan(first_mp, df[df["is_multiple_placements"]]["n"].max() + 0.5,
                        alpha=0.06, color=C["mp"], label=f"labelled region (n >= {first_mp})")
        axes[1].axvline(first_mp, color="orange", lw=1.5, ls="--")
    hr = df[df["is_hex_resonance"]]
    axes[1].scatter(hr["n"], hr["k_n"], s=160, marker="*", color=C["k6"],
                    zorder=6, edgecolors="white", lw=0.5,
                    label="Hexagonal Resonance - Snap-to-Perfection")
    axes[1].set_yticks([3, 4, 5, 6]); axes[1].set_ylim(2.3, 7.0)
    axes[1].set_xlabel("n (Number of Vertices)", fontweight="bold")
    axes[1].set_ylabel("k(n)", fontweight="bold")
    axes[1].legend(fontsize=8, loc="lower right")
    axes[1].set_title("k(n) with the labelled region highlighted", fontsize=11)
    fig.tight_layout()
    return fig

# -- Plot 7: s(n) Formula Analysis (4-panel) -------------------------------
def fig_formula_analysis(df: pd.DataFrame) -> plt.Figure:
    n_vals   = df["n"].values
    s_actual = df["s_n"].values.astype(float)
    n_cont   = np.arange(n_vals.min(), n_vals.max() + 2)

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        "s(n) Vertex Skipping - Exact Formula  s(n) = max(0, ceil(n/6) - 2)\n"
        "Muhammad Zaid Bilal - Polygon Conjoinability Research",
        fontsize=12, fontweight="bold", y=1.01)

    k6 = df[df["is_hex_resonance"]]

    # Panel A - Data + formulas
    ax = axes[0, 0]
    ax.scatter(n_vals, s_actual, color=C["s_line"], s=28, zorder=5,
               edgecolors="white", lw=0.4, label="Data s(n)")
    ax.plot(n_cont, [s_exact(n) for n in n_cont], color=C["refined"],
            lw=1.5, ls="-", label="Exact: max(0, ceil(n/6) - 2)")
    ax.plot(n_cont, [s_simple(n) for n in n_cont], color=C["approx"],
            lw=1.3, ls=":", label="Old approx: max(0, floor((n-6)/6))")
    ax.scatter(k6["n"], k6["s_n"], s=70, marker="*", color=C["k6"],
               zorder=6, edgecolors="white", lw=0.4, label="HR points (6 | n)")
    ax.set_title("A - Data vs. Formulas", fontsize=11, fontweight="bold")
    ax.set_xlabel("n"); ax.set_ylabel("s(n)")
    ax.legend(fontsize=7.5)
    ax.set_ylim(-0.5, s_actual.max() + 3)

    # Panel B - Residuals
    ax = axes[0, 1]
    err_old = s_actual - np.array([s_simple(n) for n in n_vals])
    err_new = s_actual - np.array([s_exact(n) for n in n_vals])
    ax.bar(n_vals, err_old, width=0.8, color=C["approx"], alpha=0.75,
           label="Old approx error (-1 at every multiple of 6)")
    ax.plot(n_vals, err_new, color=C["refined"], lw=1.6, marker="o", ms=2.5,
            label="Exact-formula error (0 when data is clean)")
    ax.axhline(0, color="black", lw=0.8)
    ax.set_title("B - Residuals: Data - Formula", fontsize=11, fontweight="bold")
    ax.set_xlabel("n"); ax.set_ylabel("Error (data - formula)")
    ax.legend(fontsize=8)

    # Panel C - s(6m) vs m
    ax = axes[1, 0]
    hr_e = k6.copy(); hr_e["m"] = hr_e["n"] // 6
    ax.scatter(hr_e["m"], hr_e["s_n"], s=45, color=C["k6"], zorder=5,
               edgecolors="white", lw=0.4, label="Data s(6m)")
    m_r = np.arange(1, max(hr_e["m"].max() if len(hr_e) else 2, 2) + 2)
    ax.plot(m_r, np.maximum(0, m_r - 2), ls="--", color="#805AD5", lw=1.5,
            label="s = m - 2  (all m >= 2)")
    if len(hr_e):
        sel = hr_e[hr_e["n"].apply(_label_ok)]
        for _, row in sel.iterrows():
            ax.text(row["m"] + 0.2, row["s_n"] - 0.9, f"n={row['n']}", fontsize=7, color=C["k6"])
    ax.set_title("C - s(6m) at Hexagonal Resonance vs. m", fontsize=11, fontweight="bold")
    ax.set_xlabel("m  (n = 6m)"); ax.set_ylabel("s(n)")
    ax.legend(fontsize=7.5)

    # Panel D - s(6m)/m -> 1
    ax = axes[1, 1]
    if len(hr_e):
        hr_e["ratio"] = hr_e["s_n"] / hr_e["m"]
        ax.scatter(hr_e["m"], hr_e["ratio"], s=45, color=C["k6"], zorder=5,
                   edgecolors="white", lw=0.4, label="s(n)/m data")
    m_cont = np.linspace(1, m_r.max(), 400)
    ax.plot(m_cont, np.maximum(0, (m_cont - 2) / m_cont), color="#805AD5", lw=1.4,
            ls="-.", label="(m-2)/m curve")
    ax.axhline(1.0, color="#2C7A7B", lw=1.4, ls="--", label="Limit  s/m -> 1")
    ax.set_title("D - Ratio s(6m)/m -> 1 as m -> infinity", fontsize=11, fontweight="bold")
    ax.set_xlabel("m  (n = 6m)"); ax.set_ylabel("s(n) / m")
    ax.set_ylim(-0.1, 1.15)
    ax.legend(fontsize=7.5)

    fig.tight_layout()
    return fig

# -- Plot 9: internal angle vs s(n)  (was spreadsheet Chart3 + Chart4) -------
def fig_angle_vs_s(df: pd.DataFrame) -> plt.Figure:
    kcol = {3: "#68D391", 4: C["mp"], 5: C["k_line"], 6: C["k6"]}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    for ax, ycol, ylab in ((axes[0], "angle_deg", "Internal angle (degrees)"),
                           (axes[1], "angle_rad", "Internal angle (radians)")):
        ax.plot(df["s_n"], df[ycol], color="#B8C3D6", lw=0.8, zorder=1)      # path in order of n
        for k, sub in df.groupby("k_n"):
            ax.scatter(sub["s_n"], sub[ycol], s=28, color=kcol.get(int(k), C["other"]),
                       edgecolors="white", lw=0.3, label=f"k = {int(k)}", zorder=3)
        ax.set_xlabel("s(n) - number of vertices skipped", fontweight="bold")
        ax.set_ylabel(ylab, fontweight="bold")
    axes[0].legend(title="Conjoinability", fontsize=8)
    fig.suptitle("Internal angle of the regular n-gon vs. number of vertices skipped",
                 fontweight="bold", fontsize=13)
    fig.tight_layout()
    return fig

# -- Plot 10: tension and its sawtooth limit --------------------------------
def fig_contact_gap(df: pd.DataFrame) -> plt.Figure:
    """Formal H4 / H5: tension tau(n) = gap between adjacent tight neighbours, in sides (report Thm 7.1)."""
    ns = [int(n) for n in df["n"] if n >= 7]
    g = np.array([pl.contact_gap(n) for n in ns])
    saw = np.array([pl.sawtooth_limit(n) for n in ns])
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
    ax = axes[0]
    ax.scatter(ns, saw, s=22, marker="_", color=C["refined"], zorder=2, label="limit (sqrt3/6)*((-n) mod 6)")
    ax.scatter(ns, g, s=14, color=C["k_line"], zorder=3, label="tension tau(n)")
    zeros = [n for n, v in zip(ns, g) if v < 1e-9]
    ax.scatter(zeros, [0] * len(zeros), s=45, marker="*", color=C["k6"], zorder=4, label="tau = 0  (6 divides n)")
    ax.set_ylabel("tension: gap between adjacent neighbours (sides)", fontweight="bold")
    ax.set_title("Tension tau(n): zero exactly at the hexagonal resonances, sawtooth of period 6 in the limit",
                 fontweight="bold")
    ax.legend(fontsize=8.5, loc="upper right")
    axes[1].scatter(ns, np.array(ns) * np.abs(g - saw), s=10, color=C["s_line"])
    axes[1].set_ylabel("n * |tau - limit|", fontweight="bold")
    axes[1].set_xlabel("n (Number of Vertices)", fontweight="bold")
    axes[1].set_title("The error is O(1/n): n * error stays bounded", fontsize=10)
    fig.tight_layout()
    return fig

# -- Plot 8: Plotly interactive 3D -----------------------------------------
def fig_plotly_3d(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    for state in df["tension_state"].unique():
        sub = df[df["tension_state"] == state]
        fig.add_trace(go.Scatter3d(
            x=sub["n"], y=sub["angle_rad"], z=sub["k_n"],
            mode="markers",
            name=str(state).strip() or "Normal",
            marker=dict(size=6, color=tension_color(state), opacity=0.85,
                        line=dict(color="white", width=0.4)),
            text=sub["hover"], hoverinfo="text",
        ))
    fig.update_layout(
        title="Interactive 3D: n x Internal Angle -> k(n), coloured by Tension State",
        scene=dict(
            xaxis_title="n (Vertices)",
            yaxis_title="Internal Angle alpha (rad)",
            zaxis_title="k(n) Conjoinability",
            bgcolor=C["bg"],
        ),
        height=620,
        margin=dict(l=0, r=0, b=0, t=50),
        paper_bgcolor=C["bg"],
        legend=dict(font=dict(size=9)),
    )
    return fig

# -- HR Sheet: exterior angle ratio plot -----------------------------------
def fig_hr_sheet(hr_df: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].plot(hr_df["n"], hr_df["int_angle_deg"], color=C["k_line"],
                 marker="o", ms=5, lw=2)
    axes[0].set_title("Interior Angle vs. n (multiples of 6)", fontweight="bold")
    axes[0].set_xlabel("n"); axes[0].set_ylabel("Interior Angle (deg)")

    axes[1].plot(hr_df["n"], hr_df["ext_ratio"], color=C["s_line"],
                 marker="s", ms=5, lw=2)
    axes[1].axhline(1.0, color="gray", ls="--", lw=1.0)
    axes[1].set_title("Exterior Angle Ratio (/ previous mult-of-6) vs. n", fontweight="bold")
    axes[1].set_xlabel("n"); axes[1].set_ylabel("Ratio")

    fig.suptitle("Sheet5 - HR Polygon Angle Analysis", fontweight="bold", fontsize=13)
    fig.tight_layout()
    return fig

# -- Chart sheets: s(n) vs angle --------------------------------------------
def fig_chart_sheet(chart_df: pd.DataFrame, y_col: str, y_label: str, title: str) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(10, 5))
    for sval in sorted(chart_df["s_n"].unique()):
        sub = chart_df[chart_df["s_n"] == sval]
        ax.scatter(sub["s_n"], sub[y_col], label=f"s={sval}", s=60, alpha=0.8)
    ax.set_title(title, fontweight="bold")
    ax.set_xlabel("s(n) - Vertices Skipped"); ax.set_ylabel(y_label)
    ax.legend(title="s(n)", fontsize=8, ncol=2)
    fig.tight_layout()
    return fig

# ---------------------------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------------------------
def mpl_to_st(fig: plt.Figure):
    """Render a matplotlib figure in Streamlit at full width."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    buf.seek(0)
    st.image(buf, use_container_width=True)
    plt.close(fig)

# ---------------------------------------------------------------------------
# GEOMETRIC SOLVER TAB (uses Polygon_solver.py)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def solve_cached(n: int) -> dict:
    """Exact geometric solution for one n (cached)."""
    sol = ps.solve(int(n))
    return dict(n=sol.n, spacing=sol.spacing, k=sol.k, s=sol.s, slack=sol.slack,
                overlap_below=sol.overlap_below, arrangement=ps.arrangement(sol.n))

def fig_arrangement(n: int, sol: dict) -> plt.Figure:
    """Central n-gon with its k neighbours; untouched central vertices drawn in red."""
    fig, ax = plt.subplots(figsize=(8, 8))
    central = ps.regular_polygon(n)
    ax.add_patch(mpatches.Polygon(central, closed=True, fc="#BEE3F8", ec=C["k_line"], lw=1.6, zorder=2))
    edge, touched = 0, set()
    for i, gap in enumerate(sol["arrangement"]):
        xs, ys = ps.neighbour(n, edge).exterior.xy
        ax.add_patch(mpatches.Polygon(list(zip(xs, ys)), closed=True,
                                      fc="#C6F6D5" if i % 2 == 0 else "#FEEBC8",
                                      ec=C["k6"] if i % 2 == 0 else C["mp"], lw=1.1, alpha=0.9, zorder=1))
        touched.update({edge % n, (edge + 1) % n})
        edge += gap
    if n <= 150:
        for i, (x, y) in enumerate(central):
            ax.scatter(x, y, s=24 if n <= 60 else 9, zorder=5,
                       color=C["k_line"] if i in touched else C["mt"])
    ax.set_xlim(-3.2, 3.2); ax.set_ylim(-3.2, 3.2); ax.set_aspect("equal"); ax.axis("off")
    ax.set_title(f"n = {n}:  k = {sol['k']} neighbours,  s = {sol['s']} untouched vertices between them "
                 f"(edge spacing {sol['spacing']}, slack {sol['slack']})", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig

def render_solver_tab(df: pd.DataFrame):
    st.subheader("Geometric Solver")
    if not SOLVER_OK:
        st.error(f"`Polygon_solver` could not be imported ({SOLVER_ERR}). "
                 "Keep `Polygon_solver.py` next to this script and run `pip install shapely`.")
        return
    st.markdown(
        "Neighbours are copies of the central regular n-gon attached to one full edge (reflections). "
        "**k(n)** = how many fit without overlapping; **s(n)** = untouched vertices of the central polygon "
        "between two adjacent neighbours at the tightest packing. The solver finds the smallest "
        "non-overlapping edge spacing by exact polygon intersection, independently of the spreadsheet.")

    # ---- A: one polygon -----------------------------------------------------
    st.markdown("#### A - Solve and draw one polygon")
    n = int(st.number_input("n (number of vertices)", min_value=3, max_value=600, value=25, step=1, key="solver_n"))
    sol = solve_cached(n)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("k(n)", sol["k"]); c2.metric("s(n)", sol["s"])
    c3.metric("min edge spacing", sol["spacing"]); c4.metric("slack edges", sol["slack"])
    row = df[df["n"] == n]
    if len(row):
        r = row.iloc[0]
        if (int(r["k_n"]), int(r["s_n"])) == (sol["k"], sol["s"]):
            st.success(f"Data row n = {n} matches the solver (k = {sol['k']}, s = {sol['s']}).")
        else:
            st.error(f"Data row n = {n} says k = {int(r['k_n'])}, s = {int(r['s_n'])}, "
                     f"but the geometry gives k = {sol['k']}, s = {sol['s']}.")
    else:
        st.info(f"n = {n} is not in the loaded dataset.")
    arr = sol["arrangement"]
    arr_txt = str(arr) if len(arr) <= 24 else f"{arr[:12]} ... ({len(arr)} spacings)"
    st.caption(f"Closed forms: k = {ps.k_closed(n)}, s = {ps.s_closed(n)}.  "
               f"One valid arrangement (edge spacings, sum = n): {arr_txt}.  "
               "Red dots = central vertices touched by no neighbour.")
    mpl_to_st(fig_arrangement(n, sol))

    # ---- B: verify the dataset ---------------------------------------------
    st.divider()
    st.markdown("#### B - Check the loaded dataset against the exact solver")
    lo, hi = int(df["n"].min()), int(df["n"].max())
    n_hi = hi if hi <= lo else int(st.slider("Check rows up to n =", min_value=lo, max_value=hi,
                                             value=hi, key="solver_nhi"))
    if st.button("Run geometric check", key="solver_check"):
        sub = df[df["n"] <= n_hi]
        bar, recs = st.progress(0.0), []
        for i, r in enumerate(sub.itertuples()):
            g = solve_cached(int(r.n))
            recs.append(dict(n=int(r.n), k_data=int(r.k_n), k_geometry=g["k"],
                             s_data=int(r.s_n), s_geometry=g["s"],
                             match=(int(r.k_n) == g["k"] and int(r.s_n) == g["s"])))
            if i % 10 == 0:
                bar.progress((i + 1) / len(sub))
        bar.empty()
        st.session_state["solver_check_result"] = (n_hi, pd.DataFrame(recs))
    if "solver_check_result" in st.session_state:
        n_done, res = st.session_state["solver_check_result"]
        bad = res[~res["match"]]
        if bad.empty:
            st.success(f"All {len(res)} rows (n up to {n_done}) match the exact solver.")
        else:
            st.error(f"{len(bad)} of {len(res)} rows (n up to {n_done}) disagree with the exact solver.")
            st.dataframe(bad, use_container_width=True, hide_index=True)
        with st.expander("Full comparison"):
            st.dataframe(res, use_container_width=True, hide_index=True)

    # ---- C: generate / extend the table --------------------------------------
    st.divider()
    st.markdown("#### C - Generate or extend the table")
    st.caption("k_n, s_n, vertex_skipping and uses_skipping come from the solver. Existing tension labels are "
               "kept; new rows are marked 'Not assessed' with blank tension flags.")
    n_max = int(st.number_input("Generate rows up to n =", min_value=10, max_value=600, value=400,
                                step=10, key="solver_nmax"))
    if st.button("Build table", key="solver_build"):
        with st.spinner("Solving every n ..."):
            existing = df.drop(columns=["plot_color", "hover"], errors="ignore")
            st.session_state["solver_table"] = ps.build_table(3, n_max, existing=existing, workers=1)
    if "solver_table" in st.session_state:
        table = st.session_state["solver_table"]
        st.dataframe(table, use_container_width=True, hide_index=True)
        st.download_button("Download table CSV", data=table.to_csv(index=False).encode("utf-8"),
                           file_name="polygon_conjoinability_generated.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# PLACEMENT EXPLORER TAB (uses Polygon_placements.py)
# ---------------------------------------------------------------------------
PLACEMENT_SYMMETRY = {"Up to rotation": "rotation",
                      "Up to rotation and reflection": "dihedral",
                      "All labelled placements": "none"}

@st.cache_data(show_spinner=False)
def placements_summary(n: int) -> dict:
    m, k = pl.min_gap(n), pl.max_size(n)
    return dict(m=m, k=k, slack=n - k * m, counts=pl.count_by_size(n))

@st.cache_data(show_spinner="Enumerating placements ...")
def placements_list(n: int, size: int, symmetry: str, limit: int, order: str) -> list:
    found = pl.list_placements(n, size, symmetry, limit, order)
    return [dict(edges=p.edges, gaps=p.gaps, untouched=p.untouched, kind=p.kind, maximal=p.maximal)
            for p in found]

@st.cache_data(show_spinner=False)
def chain_list(n: int, size: int, mirror: bool) -> list:
    return [dict(edges=c.placement.edges, gaps=c.placement.gaps, untouched=c.placement.untouched,
                 kind=c.placement.kind, maximal=c.placement.maximal, label=c.label, anchor=True,
                 pocket=c.pocket_untouched)
            for c in pl.chain_placements(n, size, mirror)]

@st.cache_data(show_spinner=False)
def neighbour_xy(n: int, edge: int) -> list:
    xs, ys = ps.neighbour(n, edge).exterior.xy
    return list(zip(xs, ys))

def _draw_placement(ax, n: int, rec: dict, detail: bool = True):
    """Central n-gon (blue), neighbours (green / orange), untouched central vertices (red)."""
    edges, t = rec["edges"], len(rec["edges"])
    ax.add_patch(mpatches.Polygon(ps.regular_polygon(n), closed=True, fc="#BEE3F8",
                                  ec=C["k_line"], lw=1.4 if detail else 0.8, zorder=2))
    touched = set()
    for i, e in enumerate(edges):
        is_ba = bool(rec.get("anchor")) and e == 0          # the fixed neighbour BA is drawn in red
        xy = neighbour_xy(n, e)
        ax.add_patch(mpatches.Polygon(xy, closed=True,
                                      fc="#FED7D7" if is_ba else ("#C6F6D5" if i % 2 == 0 else "#FEEBC8"),
                                      ec="#C53030" if is_ba else (C["k6"] if i % 2 == 0 else C["mp"]),
                                      lw=(2.2 if detail else 1.4) if is_ba else (1.1 if detail else 0.6),
                                      alpha=0.95, zorder=1))
        if is_ba:
            cx = sum(p[0] for p in xy[:-1]) / (len(xy) - 1)
            cy = sum(p[1] for p in xy[:-1]) / (len(xy) - 1)
            ax.text(cx, cy, "BA", ha="center", va="center", color="#C53030", zorder=7,
                    fontsize=13 if detail else 8, fontweight="bold")
        touched.update({e % n, (e + 1) % n})
    if detail:
        if n <= 150:
            for i, (x, y) in enumerate(ps.regular_polygon(n)):
                ax.scatter(x, y, s=24 if n <= 60 else 9, zorder=5,
                           color=C["k_line"] if i in touched else C["mt"])
        for i, e in enumerate(edges):                   # label each gap with its untouched vertices
            nxt = edges[(i + 1) % t] + (n if i == t - 1 else 0)
            gap = nxt - e if t > 1 else n
            ang = 2 * math.pi * ((e + 1 + nxt) / 2) / n
            ax.text(1.16 * math.cos(ang), 1.16 * math.sin(ang), f"s={max(0, gap - 2)}",
                    ha="center", va="center", fontsize=8, color=C["mt"], zorder=6,
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    ax.set_xlim(-3.2, 3.2); ax.set_ylim(-3.2, 3.2); ax.set_aspect("equal"); ax.axis("off")

def fig_placement(n: int, rec: dict) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8, 8))
    _draw_placement(ax, n, rec, detail=True)
    extra = f", BA fixed, {rec['label']}" if rec.get("label") else ""
    ax.set_title(f"n = {n}: {len(rec['edges'])} neighbours, gaps {'-'.join(map(str, rec['gaps']))}  "
                 f"({rec['kind']}{extra})", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig

def fig_placement_grid(n: int, recs: list, cols: int = 4) -> plt.Figure:
    rows = math.ceil(len(recs) / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(3.1 * cols, 3.3 * rows), squeeze=False)
    for ax in axes.ravel():
        ax.axis("off")
    for ax, (i, rec) in zip(axes.ravel(), enumerate(recs, start=1)):
        _draw_placement(ax, n, rec, detail=False)
        ax.set_title(f"#{i}  {rec['label'] + '  ' if rec.get('label') else ''}{'-'.join(map(str, rec['gaps']))}", fontsize=9)
    fig.tight_layout()
    return fig

def _render_chain_mode(df: pd.DataFrame):
    st.markdown(
        "Fix one neighbour on edge 0 (**BA**, red). A **tight chain** has every gap equal to the minimum *m* "
        "except one gap, the **pocket**, which takes all the slack. Walking from BA you meet `ahead` tight "
        "neighbours before the pocket and `behind` the other way round (ahead + behind = neighbours - 1). "
        "Mirror images are one placement, so for n = 34 the placements are 4+0, 3+1 and 2+2. "
        "When 6 divides n there is no slack: the single perfect ring.")
    c1, c2 = st.columns(2)
    with c1:
        n = int(st.number_input("n - vertices of the central polygon", min_value=3, max_value=400,
                                value=34, step=1, key="ch_n"))
        info = placements_summary(n)
        k = info["k"]
        sizes = list(range(1, k + 1))
        size = st.selectbox("Number of neighbours", sizes, index=len(sizes) - 1, key=f"ch_size_{n}",
                            format_func=lambda t: f"{t} (the maximum, k)" if t == k else str(t))
    with c2:
        mirror = st.checkbox("Treat mirror images (about BA's axis) as the same placement", value=True, key="ch_mirror")

    recs = chain_list(n, size, mirror)
    if not recs:
        st.warning("No tight chain of that size.")
        return
    slack = n - size * info["m"]
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("min gap m", info["m"]); m2.metric("max neighbours k", k)
    m3.metric("slack (n - size*m)", slack); m4.metric("pocket (untouched vertices)", recs[0]["pocket"])
    m5.metric("placements with BA fixed", len(recs))
    st.caption(f"{len(recs)} tight-chain placement(s), "
               f"{'mirror images identified' if mirror else 'mirror images listed separately'}: "
               + ", ".join(r["label"] for r in recs) + ".")

    st.markdown("#### Overview")
    mpl_to_st(fig_placement_grid(n, recs[:24]))
    st.markdown("#### One placement in detail")
    pick = 1 if len(recs) == 1 else int(st.slider("Placement #", 1, len(recs), 1, key=f"ch_pick_{n}_{size}_{mirror}"))
    mpl_to_st(fig_placement(n, recs[pick - 1]))
    st.caption("BA is red. Red dots / labels: central vertices touched by no neighbour; the pocket is the gap with the most.")

    st.markdown("#### Table")
    table = pd.DataFrame([{"#": i, "ahead+behind": r["label"], "kind": r["kind"],
                           "gaps": "-".join(map(str, r["gaps"])),
                           "untouched per gap": "-".join(map(str, r["untouched"])),
                           "edges": " ".join(map(str, r["edges"]))} for i, r in enumerate(recs, start=1)])
    st.dataframe(table, use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    with left:
        if st.button("Verify these placements by exact geometry", key="ch_verify"):
            ok = [pl.verify_placement_geometry(n, r["edges"]) for r in recs]
            (st.success if all(ok) else st.error)(
                f"{sum(ok)} of {len(ok)} placements checked: no two neighbours overlap."
                if all(ok) else f"{len(ok) - sum(ok)} placement(s) have overlapping neighbours.")
    with right:
        st.download_button("Download table as CSV", data=table.to_csv(index=False).encode("utf-8"),
                           file_name=f"chain_placements_n{n}_size{size}.csv", mime="text/csv")

    with st.expander("Compare with the 'Multiple Placements (N)' labels in the data"):
        lab = df[df["tension_state"].str.lower().str.contains("multiple placement", na=False)].copy()
        if lab.empty:
            st.info("The loaded data has no 'Multiple Placements' labels.")
        else:
            lab["label_N"] = lab["tension_state"].str.extract(r"\((\d+)\)")[0].astype(float)
            lab["computed"] = lab["n"].apply(lambda v: pl.count_chain(int(v)))
            lab["match"] = lab["label_N"] == lab["computed"]
            show_cols = lab[["n", "k_n", "tension_state", "label_N", "computed", "match"]]
            bad = show_cols[~show_cols["match"]]
            if bad.empty:
                st.success(f"All {len(show_cols)} labelled rows agree with the computed number of placements.")
            else:
                st.warning(f"{len(bad)} of {len(show_cols)} labelled rows differ from the computed number of "
                           "tight-chain placements (largest size, BA fixed, mirror images identified).")
            st.dataframe(show_cols, use_container_width=True, hide_index=True)

def render_placements_tab(df: pd.DataFrame):
    st.subheader("Placement Explorer")
    if not (SOLVER_OK and PLACEMENTS_OK):
        st.error(f"`Polygon_placements` could not be imported ({PLACEMENTS_ERR or SOLVER_ERR}). Keep "
                 "`Polygon_solver.py` and `Polygon_placements.py` next to this script and run `pip install shapely`.")
        return
    st.markdown(
        "A **placement** is a set of edges of the central n-gon that each carry a neighbour (a reflected copy "
        "of the central polygon). **Overlap on top of another polygon is invalid; touching is allowed.** "
        "Two kinds of valid placement occur: **open** (neighbours stay apart, like the 25-gon) and "
        "**perfect ring** (each neighbour shares an edge with the next, like the 36-gon; only when 6 divides n). "
        "Consecutive chosen edges must be at least *m* apart, where *m* is the minimum non-overlapping edge "
        "spacing, so a placement is described by its cyclic **gaps** (each >= m, summing to n).")

    mode = st.radio("What to explore", ["Tight chains with BA fixed", "All valid placements"],
                    horizontal=True, key="pl_mode")
    if mode.startswith("Tight"):
        _render_chain_mode(df)
        return

    c1, c2 = st.columns(2)
    with c1:
        n = int(st.number_input("n - vertices of the central polygon", min_value=3, max_value=400,
                                value=34, step=1, key="pl_n"))
        info = placements_summary(n)
        k = info["k"]
        sizes = list(range(1, k + 1))
        size = st.selectbox("Number of neighbours", sizes, index=len(sizes) - 1, key=f"pl_size_{n}",
                            format_func=lambda t: f"{t} (the maximum, k)" if t == k else str(t))
    with c2:
        sym_label = st.radio("Count placements", list(PLACEMENT_SYMMETRY), key="pl_sym",
                             help="Rotations (and reflections) of the same arrangement are the same pattern.")
        symmetry = PLACEMENT_SYMMETRY[sym_label]
        order = st.selectbox("Order", ["Most balanced first", "Lexicographic"], key="pl_order")
        limit = int(st.number_input("Show at most", min_value=1, max_value=200, value=12, step=1, key="pl_limit"))

    labelled = pl.count_labelled(n, size)
    rot, dih = pl.count_classes(n, size)
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("min gap m", info["m"]); m2.metric("max neighbours k", k); m3.metric("slack (n - k*m)", info["slack"])
    m4.metric("labelled", f"{labelled:,}"); m5.metric("up to rotation", f"{rot:,}"); m6.metric("up to rot. + refl.", f"{dih:,}")

    total = {"rotation": rot, "dihedral": dih, "none": labelled}[symmetry]
    order_key = "balanced" if order.startswith("Most") else "lexicographic"
    recs = placements_list(n, size, symmetry, limit, order_key)
    if not recs:
        st.warning("No valid placement of that size.")
        return
    note = f"Showing {len(recs)} of {total:,} placements ({sym_label.lower()}), "
    if order_key == "balanced" and total > 20000:
        note += "in lexicographic order (too many to sort by balance)."
    else:
        note += "most balanced gap pattern first." if order_key == "balanced" else "in lexicographic order of the gaps."
    st.caption(note)

    table = pd.DataFrame([{"#": i, "kind": r["kind"], "gaps": "-".join(map(str, r["gaps"])),
                           "untouched per gap": "-".join(map(str, r["untouched"])),
                           "edges": " ".join(map(str, r["edges"])), "maximal": r["maximal"]}
                          for i, r in enumerate(recs, start=1)])

    st.markdown("#### Overview")
    mpl_to_st(fig_placement_grid(n, recs[:24]))
    if len(recs) > 24:
        st.caption("The thumbnail grid shows the first 24; the table below lists all of them.")

    st.markdown("#### One placement in detail")
    pick = 1 if len(recs) == 1 else int(st.slider("Placement #", 1, len(recs), 1,
                                                  key=f"pl_pick_{n}_{size}_{symmetry}_{order_key}_{limit}"))
    mpl_to_st(fig_placement(n, recs[pick - 1]))
    st.caption("Red dots / labels: central vertices touched by no neighbour (s = untouched vertices in that gap).")

    st.markdown("#### Table")
    st.dataframe(table, use_container_width=True, hide_index=True)
    left, right = st.columns(2)
    with left:
        if st.button("Verify these placements by exact geometry", key="pl_verify"):
            ok = [pl.verify_placement_geometry(n, r["edges"]) for r in recs]
            (st.success if all(ok) else st.error)(
                f"{sum(ok)} of {len(ok)} placements checked: no two neighbours overlap."
                if all(ok) else f"{len(ok) - sum(ok)} placement(s) have overlapping neighbours.")
    with right:
        st.download_button("Download table as CSV", data=table.to_csv(index=False).encode("utf-8"),
                           file_name=f"placements_n{n}_size{size}.csv", mime="text/csv")

    st.markdown("#### How many placements of each size")
    st.dataframe(info["counts"], use_container_width=True, hide_index=True)

def main():
    # -- Sidebar: file upload ------------------------------------------------
    st.sidebar.title("Polygon Conjoinability")
    st.sidebar.markdown("**Muhammad Zaid Bilal - May 2026**")
    st.sidebar.divider()

    uploaded = st.sidebar.file_uploader(
        "Upload Excel (.xlsx) or cleaned CSV", type=["xlsx", "csv"],
        help="Upload the corrected spreadsheet / CSV, or the app will look in the same folder for 'spreadsheet_kn_corrected_final.xlsx', 'Copy of spreadsheet_kn.xlsx', then 'polygon_conjoinability_Sheet1.csv'.",
    )

    # Resolve file source
    if uploaded is not None:
        file_src = uploaded
        file_label = uploaded.name
    else:
        default = next((p for p in ("spreadsheet_kn_corrected_final.xlsx",
                                    "spreadsheet_kn_corrected.xlsx", "Copy of spreadsheet_kn.xlsx",
                                    "polygon_conjoinability_Sheet1.csv", "polygon_conjoinability_Sheet1_corrected.csv") if os.path.exists(p)), None)
        if default:
            file_src = default
            file_label = default
        else:
            st.warning("No file uploaded. Please upload your Excel file in the sidebar.")
            st.stop()

    # -- Load workbook & list sheets ----------------------------------------
    @st.cache_data(show_spinner="Reading workbook...")
    def load_workbook(src):
        src_name = getattr(src, "name", src if isinstance(src, str) else "")
        if str(src_name).lower().endswith(".csv"):
            return {"CSV": pd.read_csv(src)}
        xf = pd.ExcelFile(src, engine="openpyxl")      # explicit engine: works whatever the extension
        sheets = {}
        for name in xf.sheet_names:
            raw = xf.parse(name, header=0)
            sheets[name] = raw
        return sheets

    sheets = load_workbook(file_src)
    sheet_names = list(sheets.keys())

    # -- Sidebar: sheet selector --------------------------------------------
    st.sidebar.markdown("### Sheet Selection")

    classified = {n: classify_sheet(sheets[n]) for n in sheet_names}
    main_candidates = [n for n, k in classified.items() if k == "main"]
    default_idx = 0
    if main_candidates:
        default_idx = sheet_names.index(main_candidates[0])

    primary_sheet = st.sidebar.selectbox(
        "Select PRIMARY data sheet",
        options=sheet_names,
        index=default_idx,
        help="This sheet must contain Vertices / k(n) / s(n) columns.",
    )

    st.sidebar.markdown("---")
    extra_sheets = st.sidebar.multiselect(
        "Also show supplementary sheets",
        options=[n for n in sheet_names if n != primary_sheet],
        default=[n for n in sheet_names
                 if n != primary_sheet and classified[n] in ("hr_angles","chart_deg","chart_rad")],
    )

    # -- Parse primary sheet ------------------------------------------------
    raw_primary = sheets[primary_sheet]
    sheet_kind  = classified[primary_sheet]

    if sheet_kind != "main":
        st.error(
            f"Sheet '{primary_sheet}' does not appear to be a main data sheet (detected type: '{sheet_kind}'). Please pick a sheet that contains Vertices / k(n) columns."
        )
        st.stop()

    df = parse_main_sheet(raw_primary)
    eda = compute_eda(df)
    insights = generate_insights(df, eda)

    # -- Sidebar: quick stats -----------------------------------------------
    st.sidebar.markdown("### Quick Stats")
    st.sidebar.metric("Data rows",  eda["n_rows"])
    st.sidebar.metric("n range",    f"{eda['n_range'][0]} - {eda['n_range'][1]}")
    st.sidebar.metric("HR points",  len(eda["hr_ns"]))
    st.sidebar.metric("k=6 share",  f"{eda['pct_k6']}%")
    st.sidebar.metric("Max s(n)",   eda["s_max"])
    if df.attrs.get("n_rebuilt"):
        st.sidebar.info(f"The workbook has no cached values in the Vertices column; n was rebuilt for "
                        f"{df.attrs['n_rebuilt']} rows. Re-save the file in Excel / Sheets, or use the CSV.")
    _bad = sorted(set(eda["bad_s_ns"]) | set(eda["bad_k_ns"]))
    if _bad:
        st.sidebar.warning(f"{len(_bad)} row(s) disagree with k(n)=floor(n/ceil(n/6)) / s(n)=max(0,ceil(n/6)-2): n = {_bad[:12]}{' ...' if len(_bad) > 12 else ''}")
    else:
        st.sidebar.success("All rows match the exact k(n) and s(n) formulas.")
    st.sidebar.markdown("---")

    # -- Sidebar: plot toggles ---------------------------------------------
    st.sidebar.markdown("### Show Plots")
    show = {
        "k_vs_n"   : st.sidebar.checkbox("1 - k(n) vs n",                 True),
        "s_vs_n"   : st.sidebar.checkbox("2 - s(n) vs n",                 True),
        "dual"     : st.sidebar.checkbox("3 - Dual-axis k & s",           True),
        "heatmap"  : st.sidebar.checkbox("4 - Heatmap",                   True),
        "s_vs_k"   : st.sidebar.checkbox("5 - s(n) vs k(n)",              True),
        "isomer"   : st.sidebar.checkbox("6 - Multiple-Placement labels", True),
        "formula"  : st.sidebar.checkbox("7 - s(n) Formula Analysis",     True),
        "3d"       : st.sidebar.checkbox("8 - Interactive 3D (Plotly)",   True),
        "angle"    : st.sidebar.checkbox("9 - Internal angle vs s(n)",    True),
        "gap"      : st.sidebar.checkbox("10 - Tension tau(n)",          True),
    }

    # -----------------------------------------------------------------------
    # MAIN PAGE
    # -----------------------------------------------------------------------
    st.title("Polygon Conjoinability Research")
    st.markdown(
        f"Primary sheet: `{primary_sheet}`  |  File: `{file_label}`  |  Rows loaded: {eda['n_rows']}  |  n range: {eda['n_range'][0]} - {eda['n_range'][1]}"
    )
    st.divider()

    # -- Tabs ---------------------------------------------------------------
    tab_eda, tab_clean, tab_insights, tab_plots, tab_solver, tab_place, tab_supp, tab_raw = st.tabs([
        "EDA",
        "Data Cleaning",
        "Insights",
        "Visualisations",
        "Geometric Solver",
        "Placements",
        "Supplementary Sheets",
        "Raw Data",
    ])

    # -- TAB: EDA ------------------------------------------------------------
    with tab_eda:
        st.subheader("Exploratory Data Analysis")

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total rows",        eda["n_rows"])
        col2.metric("n min -> max",     f"{eda['n_range'][0]} -> {eda['n_range'][1]}")
        col3.metric("Hexagonal Res. pts",len(eda["hr_ns"]))
        col4.metric("First MP label at n", str(eda["first_mp"]) if eda["first_mp"] else "None")

        col5, col6, col7, col8 = st.columns(4)
        col5.metric("k=6 share",  f"{eda['pct_k6']}%")
        col6.metric("k=5 share",  f"{eda['pct_k5']}%")
        col7.metric("k=4 share",  f"{eda['pct_k4']}%")
        col8.metric("Max s(n)",   eda["s_max"])

        st.divider()

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### k(n) Distribution")
            k_dist_df = pd.DataFrame.from_dict(eda["k_dist"], orient="index",
                                               columns=["count"])
            k_dist_df.index.name = "k(n)"
            st.dataframe(k_dist_df, use_container_width=True)

            st.markdown("#### Correlation Matrix")
            corr_df = df[["n", "k_n", "s_n", "angle_deg"]].corr().round(4)
            st.dataframe(corr_df.style.background_gradient(cmap="coolwarm", axis=None),
                         use_container_width=True)

        with c2:
            st.markdown("#### Tension State Distribution")
            ts_df = pd.DataFrame.from_dict(eda["tension_dist"], orient="index",
                                           columns=["count"])
            ts_df.index.name = "Tension State"
            ts_df = ts_df.sort_values("count", ascending=False)
            st.dataframe(ts_df, use_container_width=True)

            st.markdown("#### Formula Accuracy (s(n))")
            acc = {
                "Formula"        : ["s exact: max(0, ceil(n/6)-2)", "s old approx: floor((n-6)/6)", "k exact: floor(n/ceil(n/6))"],
                "MAE"            : [eda["exact_mae"], eda["simple_mae"], round(float((df["k_n"] - df["k_exact"]).abs().mean()), 4)],
                "Exact match %"  : [eda["exact_pct"], eda["simple_exact_pct"], eda["k_exact_pct"]],
            }
            st.dataframe(pd.DataFrame(acc), use_container_width=True, hide_index=True)

            st.markdown("#### Rows disagreeing with the model")
            bad_df = df[(df["s_n"] != df["s_exact"]) | (df["k_n"] != df["k_exact"])][
                ["n", "k_n", "k_exact", "s_n", "s_exact"]]
            if bad_df.empty:
                st.success("Every row matches k(n) = floor(n/ceil(n/6)) and s(n) = max(0, ceil(n/6)-2).")
            else:
                st.dataframe(bad_df, use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### Descriptive Statistics")
        st.dataframe(df[["n","k_n","s_n","angle_deg"]].describe().round(4),
                     use_container_width=True)

        st.markdown("#### Hexagonal Resonance Points")
        st.dataframe(df[df["is_hex_resonance"]][
            ["n","k_n","s_n","angle_deg","tension_state"]],
            use_container_width=True, hide_index=True)

    # -- TAB: DATA CLEANING -------------------------------------------------
    with tab_clean:
        st.subheader("Data Cleaning & Preprocessing Log")
        st.markdown("""
The following steps are applied automatically when the primary sheet is loaded:

| # | Step | Detail |
|---|------|--------|
| 1 | Column rename | Raw column names mapped to short aliases: `n`, `k_n`, `s_n`, `angle_str`, `tension_state` |
| 2 | Drop junk columns | `Unnamed:` columns discarded |
| 3 | Numeric coercion | `n`, `k_n`, `s_n` forced to numeric; non-parseable cells -> NaN |
| 4 | NaN drop | Rows where `n` or `k_n` is NaN are dropped |
| 5 | s_n fill | Remaining NaN in `s_n` filled with 0 (no skipping) |
| 6 | Integer cast | `n`, `k_n`, `s_n` cast to `int` |
| 7 | Tension normalise | String `"0"` and `NaN` -> `"Normal"`; whitespace stripped |
| 8 | Derived columns | `angle_rad`, `angle_deg` recomputed from `n` for accuracy |
| 9 | Boolean flags | `is_hex_resonance`, `is_max_tense`, `is_multiple_placements`, `is_phase_shift`, `is_minimally_tense`, `uses_skipping` |
| 10 | Formula cols | `s_exact`, `k_exact` (closed forms) and the superseded `s_simple` computed for every row; disagreements are flagged in the EDA tab |
| 11 | Sort | Rows sorted ascending by `n` |
| 12 | Assessed flag | Rows whose tension state is `Not assessed` (n > 55 except 174) are excluded from tension / label statistics |
""")
        st.divider()
        st.markdown("#### After-cleaning preview (first 20 rows)")
        display_cols = ["n","k_n","s_n","angle_deg","tension_state",
                        "is_hex_resonance","is_max_tense","is_multiple_placements",
                        "s_exact","k_exact"]
        st.dataframe(df[display_cols].head(20), use_container_width=True, hide_index=True)

        st.markdown("#### Null counts after cleaning")
        null_counts = df[display_cols].isnull().sum().reset_index()
        null_counts.columns = ["Column", "Null count"]
        st.dataframe(null_counts, use_container_width=True, hide_index=True)

    # -- TAB: INSIGHTS ------------------------------------------------------
    with tab_insights:
        st.subheader("Key Research Insights")
        for marker, text in insights:
            st.info(f"{marker}  {text}")

        st.divider()
        st.markdown("### Hypothesis Evolution Summary")
        with st.expander("REJECTED Hypotheses", expanded=False):
            st.error("""
H1-Original - Conjoinability Ceiling Hypothesis (REJECTED)
k(n) <= 5 for all n > 6, with lim k(n) = 5 != 6 = k(infinity).

Falsified by k(36)=6, k(42)=6, k(48)=6, k(54)=6, k(174)=6.

---
H5-Original - k-pi-gon Hypothesis (REJECTED)
A real t* in (6,7) exists such that K(t*)=6 but k(n) <= 5 for all integer n > 6.

Falsified by the same data - discrete n = 6m achieves k = 6 for all m.
""")
        with st.expander("REVISED Hypotheses", expanded=False):
            st.warning("""
H2-Original - Monotonic Vertex Skipping Hypothesis (RESTORED -> H2 Current)
s(n) is monotonically non-decreasing.

The apparent step-back s(18)=1 < s(17)=2 was a data-entry error (geometry gives s(17)=1).
After correction s(n) is non-decreasing, so the original hypothesis stands.

---
H3-Original - Maximally Tense = Instability Threshold (REFINED -> H4 Current)
MT states trigger transitions to higher s(n) to keep k <= 5.

Refined: MT states are conditions enabling k = 6, not signs of instability.

---
H4-Previous - Tense Perfectibility (REPLACED -> H4 Current)
All assessed k(n)=6 points for 12 < n <= 55 are labelled Maximally Tense.

The labels are hand-assigned and not a function of k (n = 13 has k = 4 and is labelled; n = 6, 12 and 174 have k = 6 and are not). Replaced by the measurable tension, for which the statement is a theorem.

---
H6-Previous - Snap-to-Perfection (REPLACED -> H6 Current)
At n >= 34, multiple placements create flexibility; HR collapses isomers to one perfect configuration.

The n >= 34 threshold and the count 2 came from the labelling. Counted exactly there are 3 tight chains with BA fixed, and multiple placements exist from n = 7.
""")
        with st.expander("CURRENT Hypotheses (H1-H6)", expanded=True):
            st.success("""
Formal statements and proofs: Polygon_Conjoinability_Proofs.pdf (theorem numbers below refer to it).

H1 - Hexagonal Resonance of the Conjoinability (Proved: Thm 3.2, Thm 4.1, Prop 4.3)
The conjoinability k(n), the largest number of non-overlapping reflected copies of the n-gon that can be conjoined to it, equals floor(n / ceil(n/6)) for every n >= 3. Hence k(n) = 6 iff 6 divides n (n >= 6).

H2 - Vertex Skipping and Slack (Proved: Thm 3.2, Thm 4.1, Thm 4.2, Cor 4.4)
Neighbours on edges at cyclic distance d overlap iff d < n/6. So s(n) = max(0, ceil(n/6) - 2), non-decreasing. The slack sigma(n) = n - k(n) ceil(n/6) equals floor(n/6) + (n mod 6) - 5 for n >= 20 with 6 not dividing n; it is 0 iff 6 divides n or n is 8, 10, 15, 20, 25.

H3 - Generating Function (Proved: Thm 6.1, Cor 6.2)
The placement polynomial P(n)(x) = sum over t of N(n,t) x^t, with N(n,t) = (n/t) C(n - t(m-1) - 1, t - 1) and m = ceil(n/6), equals the sum of the n-th powers of the roots of lambda^m = lambda^(m-1) + x. Its degree is 6 exactly when 6 divides n (the re-entry into k = 6).

H4 - Tension (Formalised: Thm 7.1 (ii))
The tension tau(n) is the clearance, in sides, between two neighbours conjoined at the minimal spacing. For n >= 7, tau(n) = 0 iff 6 divides n iff k(n) = 6. The hand-assigned Maximally Tense labels are not a function of k and are not used as evidence.

H5 - Discrete-to-Continuous Resonance (Formalised: Thm 7.1 (iii), Prop 7.2)
For n >= 7 with 6 not dividing n, |tau(n) - (sqrt(3)/6)(6 - r)| <= (kappa^2/2 + 1) pi/n, where r = n mod 6 and kappa = (6 - r)/6: a sawtooth of period 6 with zeros at the resonances (Plot 10). limsup k(n) = 6, the circle's kissing number, and liminf k(n) = 5.

H6 - Flexibility and Rigidity (Proved: Thm 5.1, Thm 5.3, Cor 5.4, Thm 5.5)
N(n,t) counts the placements of t neighbours. The extremal placement is unique up to rotation iff the slack is at most 1, i.e. iff 6 divides n or n is one of 7, 8, 9, 10, 11, 13, 15, 16, 20, 21, 25, 26, 31. With BA fixed there are ceil(k/2) tight chains when the slack is positive (3 for n = 34). Multiple placements exist at every n with positive slack, from n = 7.
""")

        st.divider()
        st.markdown("### Documented Errors & Corrections")
        errors_df = pd.DataFrame([
            ("E1", "Discontinuity at infinity",
             "lim k(n) = 5 != k(infinity) = 6",
             "k(n) oscillates, touching 6 at every 6m; no real discontinuity"),
            ("E2", "Step-back in s(n)",
             "s(18)=1 < s(17)=2, so s is not monotone",
             "Data error: s(17)=1. s(n)=max(0, ceil(n/6)-2) is non-decreasing"),
            ("E3", "k(n) <= 5 for all n > 6",
             "No discrete polygon achieves k=6",
             "Falsified by k(36)=k(42)=k(48)=k(54)=k(174)=6"),
            ("E4", "Maximally Tense = lower k",
             "MT states precede transitions to higher s",
             "MT states enable k=6 - they are conditions of peak order"),
            ("E5", "Regime change at m=29",
             "s(174)=29=m, not m-2; transition region m in [10,28] unknown",
             "Data error: s(174)=27=m-2. The formula holds for all m >= 3; no transition region"),
            ("E6", "Angle notation at n=34",
             "Listed 32*pi/34 instead of canonical form",
             "Numerically correct but style-inconsistent; no data error"),
            ("E7", "s(n) entries at n = 7-11, 14-17, 25, 26",
             "Recorded 1, 2 and 2",
             "Geometry gives 0, 1 and 3 (untouched vertices between neighbours)"),
            ("E8", "k(7) = 4",
             "Four neighbours fit around a heptagon",
             "k(7) = 3: neighbours on adjacent edges overlap (interior angle > 120 deg)"),
            ("E9", "Multiple Placements (2) at n = 34-55",
             "Two placements (counted by eye in GeoGebra)",
             "Three: tight chains with BA fixed 4+0, 3+1, 2+2 (report Thm 5.5); labels corrected to 3"),
            ("E10", "Multiple placements start at n = 34",
             "Flexibility appears only from n >= 34",
             "Tight chains with BA fixed exist at every n with slack, from n = 7; the threshold came from the labelling, not the geometry"),
        ], columns=["ID", "Name", "What Was Believed", "Correction"])
        st.dataframe(errors_df, use_container_width=True, hide_index=True)

    # -- TAB: VISUALISATIONS -----------------------------------------------
    with tab_plots:
        st.subheader("Visualisations")

        if show["k_vs_n"]:
            st.markdown("#### Plot 1 - k(n) Conjoinability vs. n")
            mpl_to_st(fig_k_vs_n(df))

        if show["s_vs_n"]:
            st.markdown("#### Plot 2 - s(n) Vertex Skipping vs. n")
            mpl_to_st(fig_s_vs_n(df))

        if show["dual"]:
            st.markdown("#### Plot 3 - Dual-Axis: k(n) & s(n)")
            mpl_to_st(fig_dual_axis(df))

        if show["heatmap"]:
            st.markdown("#### Plot 4 - Heatmap: k(n) & s(n) vs. n")
            mpl_to_st(fig_heatmap(df))

        if show["s_vs_k"]:
            st.markdown("#### Plot 5 - s(n) vs. k(n) annotated by n & Tension State")
            mpl_to_st(fig_s_vs_k(df))

        if show["isomer"]:
            st.markdown("#### Plot 6 - Rows labelled Multiple Placements")
            mpl_to_st(fig_isomer_emergence(df))

        if show["formula"]:
            st.markdown("#### Plot 7 - s(n) Formula Analysis (4-panel)")
            mpl_to_st(fig_formula_analysis(df))

        if show["3d"]:
            st.markdown("#### Plot 8 - Interactive 3D: n x alpha -> k(n)")
            st.plotly_chart(fig_plotly_3d(df), use_container_width=True)

        if show["angle"]:
            st.markdown("#### Plot 9 - Internal angle vs. vertices skipped (degrees and radians)")
            mpl_to_st(fig_angle_vs_s(df))

        if show["gap"]:
            st.markdown("#### Plot 10 - Tension tau(n) and its sawtooth limit")
            if PLACEMENTS_OK:
                mpl_to_st(fig_contact_gap(df))
            else:
                st.info("Needs Polygon_placements.py (and shapely) next to this script.")

    # -- TAB: SUPPLEMENTARY SHEETS ------------------------------------------
    with tab_supp:
        st.subheader("Supplementary Sheet Analysis")
        if not extra_sheets:
            st.info("No supplementary sheets selected. Use the sidebar to add some.")
        for sname in extra_sheets:
            st.markdown(f"---\n### Sheet: `{sname}`  (type: `{classified[sname]}`)")
            raw = sheets[sname]
            kind = classified[sname]

            if kind == "hr_angles":
                hr_df = parse_hr_sheet(raw)
                st.dataframe(hr_df.head(15), use_container_width=True, hide_index=True)
                mpl_to_st(fig_hr_sheet(hr_df))

            elif kind in ("chart_deg", "chart_rad"):
                c_df = parse_chart_sheet(raw, kind)
                y_col   = "angle_deg" if kind == "chart_deg" else "angle_rad"
                y_label = "Angle (deg)"  if kind == "chart_deg" else "Angle (rad)"
                st.dataframe(c_df.head(15), use_container_width=True, hide_index=True)
                title = (f"{'Chart3' if kind=='chart_deg' else 'Chart4'} - s(n) vs. Internal Angle ({y_label})")
                mpl_to_st(fig_chart_sheet(c_df, y_col, y_label, title))

            elif kind == "empty":
                st.warning(f"Sheet `{sname}` is empty.")

            else:
                st.dataframe(raw.head(20), use_container_width=True)

    # -- TAB: GEOMETRIC SOLVER ---------------------------------------------
    with tab_solver:
        render_solver_tab(df)

    # -- TAB: PLACEMENTS ----------------------------------------------------
    with tab_place:
        render_placements_tab(df)

    # -- TAB: RAW DATA ------------------------------------------------------
    with tab_raw:
        st.subheader("Full Cleaned Dataset")
        st.markdown(f"Showing all {len(df)} rows for sheet `{primary_sheet}`.")
        st.dataframe(df.drop(columns=["plot_color","hover"], errors="ignore"),
                     use_container_width=True, hide_index=True)

        csv = df.drop(columns=["plot_color","hover"], errors="ignore")\
                .to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download cleaned CSV",
            data=csv,
            file_name=f"polygon_conjoinability_{primary_sheet}.csv",
            mime="text/csv",
        )

if __name__ == "__main__":
    main()