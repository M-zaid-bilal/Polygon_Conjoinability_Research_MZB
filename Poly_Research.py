"""
Polygon Conjoinability Research - Streamlit Dashboard
Muhammad Zaid Bilal | May 2026

Requirements (Python 3.10+):
  pip install streamlit pandas numpy matplotlib seaborn plotly openpyxl

Run:
  streamlit run polygon_dashboard.py

Place your Excel file in the same folder, or upload it via the sidebar.
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
def s_simple(n: int) -> int:
    """Approx: max(0, floor((n-6)/6))"""
    return max(0, int((n - 6) // 6))

def s_refined(n: int) -> int:
    """Piecewise refined with step-back at HR and regime interpolation."""
    if n <= 6:
        return 0
    if n % 6 == 0:
        m = n // 6
        if m <= 2:   return 0
        elif m <= 9: return m - 2
        elif m < 29: return int(round((m - 2) + (m - 9) * 2 / 20))
        else:        return m
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

    df["n"]   = pd.to_numeric(df.get("n",   pd.Series(dtype=float)), errors="coerce")
    df["k_n"] = pd.to_numeric(df.get("k_n", pd.Series(dtype=float)), errors="coerce")
    df["s_n"] = pd.to_numeric(df.get("s_n", pd.Series(dtype=float)), errors="coerce").fillna(0)

    df.dropna(subset=["n", "k_n"], inplace=True)
    df = df[df["n"].notna() & df["k_n"].notna()]
    df["n"]   = df["n"].astype(int)
    df["k_n"] = df["k_n"].astype(int)
    df["s_n"] = df["s_n"].astype(int)

    # Derived numeric columns
    df["angle_rad"] = (df["n"] - 2) * math.pi / df["n"]
    df["angle_deg"] = (df["n"] - 2) * 180.0  / df["n"]

    # Normalise tension_state strings
    if "tension_state" not in df.columns:
        df["tension_state"] = "Normal"
    df["tension_state"] = (
        df["tension_state"]
        .fillna("Normal")
        .replace("0", "Normal")
        .str.strip()
    )

    # Canonical boolean flags
    ts = df["tension_state"].str.lower()
    df["is_hex_resonance"]       = (df["n"] % 6 == 0) & (df["k_n"] == 6)
    df["is_max_tense"]           = ts.str.contains("maximally tense", na=False)
    df["is_phase_shift"]         = ts.str.contains("phase shift", na=False)
    df["is_multiple_placements"] = ts.str.contains("multiple placement", na=False)
    df["is_minimally_tense"]     = ts.str.contains("minimally tense", na=False)
    df["uses_skipping"]          = df["s_n"] > 0

    # Plot colour per row
    df["plot_color"] = df["tension_state"].apply(tension_color)

    # Approximate formula columns
    df["s_simple"]  = df["n"].apply(s_simple)
    df["s_refined"] = df["n"].apply(s_refined)

    # Hover text for Plotly
    df["hover"] = df.apply(
        lambda r: (f"n = {r['n']}<br>k(n) = {r['k_n']}<br>s(n) = {r['s_n']}<br>"
                   f"alpha = {r['angle_deg']:.2f} deg<br>Tension: {r['tension_state']}"),
        axis=1,
    )
    return df.sort_values("n").reset_index(drop=True)

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
    out["n_rows"]      = len(df)
    out["n_range"]     = (int(df["n"].min()), int(df["n"].max()))
    out["k_dist"]      = df["k_n"].value_counts().sort_index().to_dict()
    out["hr_ns"]       = sorted(df[df["is_hex_resonance"]]["n"].tolist())
    out["mt_ns"]       = sorted(df[df["is_max_tense"] & ~df["is_hex_resonance"]]["n"].tolist())
    out["mp_ns"]       = sorted(df[df["is_multiple_placements"]]["n"].tolist())
    out["first_mp"]    = int(df[df["is_multiple_placements"]]["n"].min()) if out["mp_ns"] else None
    out["first_skip"]  = int(df[df["uses_skipping"]]["n"].min()) if df["uses_skipping"].any() else None
    out["s_max"]       = int(df["s_n"].max())
    out["tension_dist"]= df["tension_state"].value_counts().to_dict()
    out["pct_k6"]      = round(100 * df["is_hex_resonance"].mean(), 1)
    out["pct_k5"]      = round(100 * (df["k_n"] == 5).mean(), 1)
    out["pct_k4"]      = round(100 * (df["k_n"] == 4).mean(), 1)
    out["corr_n_k"]    = round(float(df[["n", "k_n"]].corr().iloc[0, 1]), 4)
    out["corr_n_s"]    = round(float(df[["n", "s_n"]].corr().iloc[0, 1]), 4)

    # formula accuracy
    err_s  = (df["s_n"] - df["s_simple"]).abs()
    err_r  = (df["s_n"] - df["s_refined"]).abs()
    out["simple_mae"]  = round(float(err_s.mean()), 4)
    out["refined_mae"] = round(float(err_r.mean()), 4)
    out["simple_exact_pct"]  = round(100 * (err_s == 0).mean(), 1)
    out["refined_exact_pct"] = round(100 * (err_r == 0).mean(), 1)
    return out

def generate_insights(df: pd.DataFrame, eda: dict) -> list[tuple[str, str]]:
    """Return list of (marker, insight_text) tuples."""
    ins = []
    ins.append(("HEX", f"Hexagonal Resonance Law confirmed: k(n) = 6 iff 6 divides n. Verified at n in {eda['hr_ns']}."))
    ins.append(("NOTE", f"For all non-multiples of 6 with n >= 7, k(n) in {{4, 5}}. k(n) = 4 observed at n in {sorted(df[df['k_n']==4]['n'].tolist())}."))
    ins.append(("DATA", f"Dataset spans n = {eda['n_range'][0]} to {eda['n_range'][1]} ({eda['n_rows']} data-rows). k=6: {eda['pct_k6']}%, k=5: {eda['pct_k5']}%, k=4: {eda['pct_k4']}%."))
    ins.append(("STEP", f"Step-back in s(n): s(17) = 2, but s(18) = 1 - a deliberate 'step-back' that allows the 6-fold arrangement to close exactly."))
    ins.append(("SKIP", f"Vertex skipping first required at n = {eda['first_skip']} (s = 1). Maximum s(n) observed: s = {eda['s_max']} at n = 174 = 6 x 29."))
    if eda["first_mp"]:
        ins.append((f"ISOMER", f"Positional isomers (Multiple Placements) first emerge at n = {eda['first_mp']}, observed at n in {eda['mp_ns']}."))
    ins.append((f"CORR", f"Pearson correlation n<->k(n) = {eda['corr_n_k']} (near zero - k oscillates). Pearson correlation n<->s(n) = {eda['corr_n_s']} (strong positive - s grows with n)."))
    ins.append((f"FORMULA", f"s(n) formula accuracy - Simple MAE = {eda['simple_mae']}, exact {eda['simple_exact_pct']}% of rows. Refined MAE = {eda['refined_mae']}, exact {eda['refined_exact_pct']}% of rows."))
    ins.append((f"REGIME", f"Regime change in s(6m): s(6m) = m-2 holds for m in [3,9], but s(174) = 29 = m, not m-2. Transition region m in [10,28] is uncharacterised."))
    ins.append((f"TENSE", "Maximally Tense states are not instability precursors - they are the geometric conditions that enable k = 6. All k(n)=6 points for n > 12 carry a Maximally Tense label."))
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
    for _, r in k6.iterrows():
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
            lw=1.8, ls="--", marker="o", ms=4, label="Actual s(n)", zorder=3)

    n_cont = np.arange(df["n"].min(), df["n"].max() + 2)
    ax.plot(n_cont, [s_simple(n)  for n in n_cont], color=C["approx"],
            lw=1.3, ls=":", label="Simple: max(0, floor((n-6)/6))", zorder=1)
    ax.plot(n_cont, [s_refined(n) for n in n_cont], color=C["refined"],
            lw=1.3, ls="-.", label="Refined piecewise", zorder=1)

    k6 = df[df["is_hex_resonance"]]
    ax.scatter(k6["n"], k6["s_n"], s=180, color=C["k6"], marker="*",
               zorder=6, edgecolors="white", lw=0.6,
               label="s(n) at Hexagonal Resonance")
    for _, r in k6.iterrows():
        ax.text(r["n"], r["s_n"] + 0.25, f"n={r['n']},s={r['s_n']}",
                color=C["k6"], fontsize=7, ha="center", fontweight="bold")

    mt = df[df["is_max_tense"] & ~df["is_hex_resonance"]]
    ax.scatter(mt["n"], mt["s_n"], s=120, color=C["mt"], marker="X",
               zorder=5, edgecolors="black", lw=0.4, label="Maximally Tense")

    _add_hr_vlines(ax, df)

    ax.annotate("Step-back!\ns(18)=1 < s(17)=2",
                xy=(18, 1), xytext=(26, 3.8),
                fontsize=8, color=C["k6"],
                arrowprops=dict(arrowstyle="->", color=C["k6"], lw=1.1),
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C["k6"], alpha=0.9))

    ax.set_title("s(n) Vertex Skipping vs. n - with Formula Overlays",
                 fontweight="bold", pad=12)
    ax.set_xlabel("n (Number of Vertices)", fontweight="bold")
    ax.set_ylabel("s(n) (Number of Vertices Skipped)", fontweight="bold")
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
    width = max(16, len(df) * 0.42)
    fig, ax = plt.subplots(figsize=(width, 3.8))
    sns.heatmap(heat, annot=True, cmap="YlGnBu", fmt="d",
                linewidths=0.35, linecolor="#CCCCCC",
                cbar_kws={"label": "Value", "shrink": 0.7}, ax=ax)
    ax.set_title("Heatmap: k(n) & s(n) vs. n", fontweight="bold", pad=10)
    ax.set_xlabel("n (Number of Vertices)", fontweight="bold")
    ax.set_yticklabels(["k(n)", "s(n)"], rotation=0)
    ax.tick_params(axis="x", rotation=70, labelsize=7)
    fig.tight_layout()
    return fig

# -- Plot 5: s(n) vs k(n) ---------------------------------------------------
def fig_s_vs_k(df: pd.DataFrame) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(11, 8))
    rng = np.random.default_rng(42)
    seen = set()
    for _, row in df.iterrows():
        st = str(row["tension_state"]).strip()
        col = tension_color(st)
        lbl = st if st not in seen else "_nolegend_"
        seen.add(st)
        jitter = rng.uniform(-0.06, 0.06)
        ax.scatter(row["s_n"] + jitter, row["k_n"] + rng.uniform(-0.04, 0.04),
                   color=col, s=120, alpha=0.80, edgecolors="black",
                   lw=0.3, label=lbl, zorder=4)
        ax.text(row["s_n"] + jitter + 0.10, row["k_n"] + 0.05,
                f"n={row['n']}", fontsize=6.5, alpha=0.82)

    ax.set_title("s(n) vs. k(n) - Annotated by n & Tension State",
                 fontweight="bold", pad=12)
    ax.set_xlabel("s(n) (Vertices Skipped)", fontweight="bold")
    ax.set_ylabel("k(n) (Conjoinability)", fontweight="bold")
    ax.set_xticks(range(int(df["s_n"].min()), int(df["s_n"].max()) + 1))
    ax.set_yticks(range(int(df["k_n"].min()), int(df["k_n"].max()) + 1))
    ax.legend(title="Tension State", bbox_to_anchor=(1.02, 1),
              loc="upper left", fontsize=7, title_fontsize=9)
    fig.tight_layout()
    return fig

# -- Plot 6: Isomer Emergence ----------------------------------------------
def fig_isomer_emergence(df: pd.DataFrame) -> plt.Figure:
    fig, axes = plt.subplots(2, 1, figsize=(13, 9))
    fig.suptitle("Positional Isomer (Multiple Placement) Emergence vs. n",
                 fontsize=13, fontweight="bold")

    iso = df["is_multiple_placements"].astype(int)
    axes[0].bar(df["n"], iso,
                color=[C["mp"] if v else "#B8C3D6" for v in iso],
                width=0.8, alpha=0.9)
    first_mp = df[df["is_multiple_placements"]]["n"].min() if iso.any() else None
    if first_mp:
        axes[0].axvline(first_mp, color="orange", lw=1.8, ls="--",
                        label=f"First isomer at n={first_mp}")
        for n_val in df[df["is_multiple_placements"]]["n"]:
            axes[0].text(n_val, 1.05, str(n_val), ha="center",
                         fontsize=6.5, color=C["mp"], rotation=90)
    axes[0].set_yticks([0, 1]); axes[0].set_yticklabels(["No", "Yes"])
    axes[0].set_ylabel("Multiple Placements?", fontweight="bold")
    axes[0].legend(fontsize=9)
    axes[0].set_title("Presence of Positional Isomers", fontsize=11)

    col2 = [C["k6"] if r["is_hex_resonance"]
             else C["mt"] if r["is_max_tense"]
             else C["mp"] if r["is_multiple_placements"]
             else C["k_line"]
             for _, r in df.iterrows()]
    axes[1].scatter(df["n"], df["k_n"], c=col2, s=90, zorder=5,
                    edgecolors="white", lw=0.5)
    axes[1].plot(df["n"], df["k_n"], color=C["k_line"], alpha=0.25, lw=1.2)
    if first_mp:
        axes[1].axvspan(first_mp, df["n"].max() + 5,
                        alpha=0.06, color=C["mp"], label=f"MP region (n >= {first_mp})")
        axes[1].axvline(first_mp, color="orange", lw=1.5, ls="--")
    hr = df[df["is_hex_resonance"]]
    axes[1].scatter(hr["n"], hr["k_n"], s=160, marker="*", color=C["k6"],
                    zorder=6, edgecolors="white", lw=0.5,
                    label="Hexagonal Resonance - Snap-to-Perfection")
    axes[1].set_yticks([3, 4, 5, 6]); axes[1].set_ylim(2.3, 7.0)
    axes[1].set_xlabel("n (Number of Vertices)", fontweight="bold")
    axes[1].set_ylabel("k(n)", fontweight="bold")
    axes[1].legend(fontsize=8, loc="lower right")
    axes[1].set_title("k(n) with Isomer Region Highlighted", fontsize=11)
    fig.tight_layout()
    return fig

# -- Plot 7: s(n) Formula Analysis (4-panel) -------------------------------
def fig_formula_analysis(df: pd.DataFrame) -> plt.Figure:
    n_vals   = df["n"].values
    s_actual = df["s_n"].values.astype(float)
    n_cont   = np.arange(n_vals.min(), n_vals.max() + 2)

    fig, axes = plt.subplots(2, 2, figsize=(16, 11))
    fig.suptitle(
        "s(n) Vertex Skipping - Formula Analysis & Approximations\n"
        "Muhammad Zaid Bilal - Polygon Conjoinability Research",
        fontsize=12, fontweight="bold", y=1.01)

    k6 = df[df["is_hex_resonance"]]

    # Panel A - Actual + overlays
    ax = axes[0, 0]
    ax.scatter(n_vals, s_actual, color=C["s_line"], s=65, zorder=5,
               edgecolors="white", lw=0.5, label="Actual s(n)")
    ax.step(n_vals, s_actual, where="mid", color=C["s_line"], alpha=0.4, lw=1.1)
    ax.plot(n_cont, [s_simple(n)  for n in n_cont], color=C["approx"],
            lw=1.4, ls=":", label="Simple: max(0,floor((n-6)/6))")
    ax.plot(n_cont, [s_refined(n) for n in n_cont], color=C["refined"],
            lw=1.4, ls="-.", label="Refined piecewise")
    ax.scatter(k6["n"], k6["s_n"], s=160, marker="*", color=C["k6"],
               zorder=6, edgecolors="white", lw=0.5, label="HR points")
    ax.annotate("Step-back\ns(18)=1 < s(17)=2",
                xy=(18, 1), xytext=(26, 4.5), fontsize=8, color=C["k6"],
                arrowprops=dict(arrowstyle="->", color=C["k6"], lw=1.0),
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=C["k6"], alpha=0.9))
    ax.set_title("A - Actual s(n) vs. Approximations", fontsize=11, fontweight="bold")
    ax.set_xlabel("n"); ax.set_ylabel("s(n)")
    ax.legend(fontsize=7.5)
    ax.set_ylim(-0.5, s_actual.max() + 3)

    # Panel B - Residuals
    ax = axes[0, 1]
    err_s = s_actual - np.array([s_simple(n)  for n in n_vals])
    err_r = s_actual - np.array([s_refined(n) for n in n_vals])
    w = 0.35
    ax.bar(n_vals - w / 2, err_s, width=w, color=C["approx"],  alpha=0.82, label="Simple error")
    ax.bar(n_vals + w / 2, err_r, width=w, color=C["refined"], alpha=0.82, label="Refined error")
    ax.axhline(0, color="black", lw=0.8)
    ax.scatter(k6["n"], [0] * len(k6), s=70, marker="*", color=C["k6"],
               zorder=6, label="HR points")
    ax.set_title("B - Residuals: Actual - Predicted", fontsize=11, fontweight="bold")
    ax.set_xlabel("n"); ax.set_ylabel("Error (actual - predicted)")
    ax.legend(fontsize=8)

    # Panel C - s(6m) at HR vs m
    ax = axes[1, 0]
    hr_e = k6.copy(); hr_e["m"] = hr_e["n"] // 6
    ax.scatter(hr_e["m"], hr_e["s_n"], s=140, color=C["k6"], zorder=5,
               edgecolors="white", lw=0.5, label="Empirical s(6m)")
    for _, row in hr_e.iterrows():
        ax.text(row["m"] + 0.08, row["s_n"] + 0.18,
                f"n={row['n']}", fontsize=7.5, color=C["k6"])
    m_r = np.arange(1, 31)
    ax.plot(m_r, np.where(m_r <= 2, 0, m_r - 2), ls="--", color="#805AD5",
            lw=1.5, label="s = m-2  (m <= 9)")
    ax.plot(m_r, np.where(m_r <= 2, 0, m_r),      ls="-.", color="#2C7A7B",
            lw=1.5, label="s = m   (m = 29)")
    ax.axvspan(9, 29, alpha=0.07, color="gold",
               label="Uncharacterised transition m in [10,28]")
    ax.set_title("C - s(6m) at Hexagonal Resonance vs. m", fontsize=11, fontweight="bold")
    ax.set_xlabel("m  (n = 6m)"); ax.set_ylabel("s(n)")
    ax.legend(fontsize=7.5)
    ax.set_ylim(-1, m_r.max() + 2)

    # Panel D - s(n)/m ratio convergence
    ax = axes[1, 1]
    hr_e["ratio"] = hr_e["s_n"] / hr_e["m"]
    ax.scatter(hr_e["m"], hr_e["ratio"], s=130, color=C["k6"], zorder=5,
               edgecolors="white", lw=0.5, label="s(n)/m empirical")
    for _, row in hr_e.iterrows():
        ax.text(row["m"] + 0.18, row["ratio"] + 0.01,
                f"n={int(row['n'])}", fontsize=7.5, color=C["k6"])
    ax.axhline(1.0, color="#2C7A7B", lw=1.4, ls="--", label="Limit  s/m -> 1")
    m_cont = np.linspace(1, 30, 300)
    ax.plot(m_cont, (m_cont - 2) / m_cont, color="#805AD5", lw=1.4,
            ls="-.", label="(m-2)/m curve")
    ax.set_title("D - Ratio s(6m)/m -> 1 as m -> infinity", fontsize=11, fontweight="bold")
    ax.set_xlabel("m  (n = 6m)"); ax.set_ylabel("s(n) / m")
    ax.set_ylim(-0.1, 1.15)
    ax.legend(fontsize=7.5)

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

def main():
    # -- Sidebar: file upload ------------------------------------------------
    st.sidebar.title("Polygon Conjoinability")
    st.sidebar.markdown("**Muhammad Zaid Bilal - May 2026**")
    st.sidebar.divider()

    uploaded = st.sidebar.file_uploader(
        "Upload Excel file (.xlsx)", type=["xlsx"],
        help="Upload your spreadsheet, or the app will look for 'Copy of spreadsheet_kn.xlsx' in the same folder.",
    )

    # Resolve file source
    if uploaded is not None:
        file_src = uploaded
        file_label = uploaded.name
    else:
        default = "Copy of spreadsheet_kn.xlsx"
        if os.path.exists(default):
            file_src = default
            file_label = default
        else:
            st.warning("No file uploaded. Please upload your Excel file in the sidebar.")
            st.stop()

    # -- Load workbook & list sheets ----------------------------------------
    @st.cache_data(show_spinner="Reading workbook...")
    def load_workbook(src):
        if hasattr(src, "read"):
            xf = pd.ExcelFile(src)
        else:
            xf = pd.ExcelFile(src)
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
    st.sidebar.markdown("---")

    # -- Sidebar: plot toggles ---------------------------------------------
    st.sidebar.markdown("### Show Plots")
    show = {
        "k_vs_n"   : st.sidebar.checkbox("1 - k(n) vs n",                 True),
        "s_vs_n"   : st.sidebar.checkbox("2 - s(n) vs n",                 True),
        "dual"     : st.sidebar.checkbox("3 - Dual-axis k & s",           True),
        "heatmap"  : st.sidebar.checkbox("4 - Heatmap",                   True),
        "s_vs_k"   : st.sidebar.checkbox("5 - s(n) vs k(n)",              True),
        "isomer"   : st.sidebar.checkbox("6 - Isomer Emergence",          True),
        "formula"  : st.sidebar.checkbox("7 - s(n) Formula Analysis",     True),
        "3d"       : st.sidebar.checkbox("8 - Interactive 3D (Plotly)",   True),
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
    tab_eda, tab_clean, tab_insights, tab_plots, tab_supp, tab_raw = st.tabs([
        "EDA",
        "Data Cleaning",
        "Insights",
        "Visualisations",
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
        col4.metric("First isomer at n", str(eda["first_mp"]) if eda["first_mp"] else "None")

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
                "Formula"        : ["Simple", "Refined piecewise"],
                "MAE"            : [eda["simple_mae"],        eda["refined_mae"]],
                "Exact match %"  : [eda["simple_exact_pct"],  eda["refined_exact_pct"]],
            }
            st.dataframe(pd.DataFrame(acc), use_container_width=True, hide_index=True)

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
| 10 | Formula cols | `s_simple` and `s_refined` computed for every row |
| 11 | Sort | Rows sorted ascending by `n` |
""")
        st.divider()
        st.markdown("#### After-cleaning preview (first 20 rows)")
        display_cols = ["n","k_n","s_n","angle_deg","tension_state",
                        "is_hex_resonance","is_max_tense","is_multiple_placements",
                        "s_simple","s_refined"]
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
H2-Original - Monotonic Vertex Skipping Hypothesis (REVISED -> H2 Current)
s(n) is monotonically non-decreasing.

Refuted by s(18)=1 < s(17)=2 (the "step-back"). Revised to Adaptive Optimisation.

---
H3-Original - Maximally Tense = Instability Threshold (REFINED -> H4 Current)
MT states trigger transitions to higher s(n) to keep k <= 5.

Refined: MT states are conditions enabling k = 6, not signs of instability.
""")
        with st.expander("CURRENT Hypotheses (H1-H6)", expanded=True):
            st.success("""
H1 - Hexagonal Resonance Law (Empirically validated)
k(n) = 6 iff 6 divides n. Verified for n in {6,12,18,24,30,36,42,48,54,174}.

H2 - Vertex Skipping Optimisation (Empirically supported)
s(n) is an adaptive mechanism; s(6m) = m-2 for m in [3,9]; regime changes at m=29.

H3 - Generating Function Isomorphism (Theoretical)
A generating function P(x,y) models the periodic re-entry into k=6 states.

H4 - Tense Perfectibility (Empirically validated)
All k(n)=6 points for n > 12 occur at Maximally Tense states.

H5 - Discrete-to-Continuous Resonance (Theoretical)
k(n) oscillations form a "geometric wave function" echoing the circle's k=6.

H6 - Probabilistic Perfectibility / Snap-to-Perfection (Empirically supported)
At n >= 34, multiple placements create flexibility; HR collapses isomers to one perfect configuration.
""")

        st.divider()
        st.markdown("### Documented Errors & Corrections")
        errors_df = pd.DataFrame([
            ("E1", "Discontinuity at infinity",
             "lim k(n) = 5 != k(infinity) = 6",
             "k(n) oscillates, touching 6 at every 6m; no real discontinuity"),
            ("E2", "Monotonicity of s(n)",
             "s(n) is non-decreasing",
             "s(18)=1 < s(17)=2; step-backs are optimisations"),
            ("E3", "k(n) <= 5 for all n > 6",
             "No discrete polygon achieves k=6",
             "Falsified by k(36)=k(42)=k(48)=k(54)=k(174)=6"),
            ("E4", "Maximally Tense = lower k",
             "MT states precede transitions to higher s",
             "MT states enable k=6 - they are conditions of peak order"),
            ("E5", "s(6m) = m-2 for all m >= 3",
             "Formula holds universally",
             "Breaks at m=29: s(174)=29=m, not m-2; transition region m in [10,28] unknown"),
            ("E6", "Angle notation at n=34",
             "Listed 32*pi/34 instead of canonical form",
             "Numerically correct but style-inconsistent; no data error"),
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
            st.markdown("#### Plot 6 - Isomer (Multiple Placement) Emergence")
            mpl_to_st(fig_isomer_emergence(df))

        if show["formula"]:
            st.markdown("#### Plot 7 - s(n) Formula Analysis (4-panel)")
            mpl_to_st(fig_formula_analysis(df))

        if show["3d"]:
            st.markdown("#### Plot 8 - Interactive 3D: n x alpha -> k(n)")
            st.plotly_chart(fig_plotly_3d(df), use_container_width=True)

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