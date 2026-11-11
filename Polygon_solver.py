"""
Polygon_solver.py - exact geometric solver for polygon conjoinability
Muhammad Zaid Bilal | Polygon Conjoinability Research

Definitions (as drawn in 25_GON.ggb)
------------------------------------
Take a regular n-gon (the *central* polygon).  A *neighbour* is a copy of the
same regular n-gon attached to one full edge of the central polygon, i.e. the
reflection of the central polygon across that edge.

    k(n)  conjoinability = how many neighbours fit around the central polygon
                           without overlapping each other.
    s(n)  vertex skipping = how many vertices of the central polygon are left
                           untouched between two adjacent neighbours when the
                           neighbours are packed as tightly as possible.

Method
------
For a central polygon with edges numbered 0..n-1, the neighbours on edge 0 and
edge m overlap or not depending only on m.  ``min_edge_spacing(n)`` finds the
smallest m for which they do not overlap (touching at a point counts as not
overlapping), by exact polygon intersection (shapely).  Then

    spacing m   = min_edge_spacing(n)
    k(n)        = n // m                (neighbours that fit around the ring)
    s(n)        = max(0, m - 2)         (untouched vertices between neighbours)

Numerically, for every n in 3..400, m = ceil(n/6), which gives the closed forms

    k(n) = floor(n / ceil(n/6))        s(n) = max(0, ceil(n/6) - 2)

``verify`` re-checks that equality for any range.  It is a numerical check, not
a proof.

What the model does NOT cover
-----------------------------
* Only the pairwise overlap of the neighbours on edge 0 and edge m is tested;
  neighbours are never allowed to overlap the central polygon (they cannot,
  being reflections).
* Tension states, phase shifts and "multiple placement" labels are not modelled.

Command line
------------
    python Polygon_solver.py solve 25
    python Polygon_solver.py verify --n-max 400
    python Polygon_solver.py table  --n-max 400 --existing polygon_conjoinability_Sheet1_corrected.csv \
                                    --out polygon_conjoinability_Sheet1_corrected.csv

Requires: numpy, pandas, shapely
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from multiprocessing import Pool

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

__all__ = [
    "regular_polygon", "neighbour", "overlap_area", "min_edge_spacing",
    "Solution", "solve", "k_closed", "s_closed", "arrangement",
    "verify", "build_table",
]

# Overlap areas are measured for polygons of circumradius 1.  Touching polygons
# intersect in a point/segment (area ~1e-17); genuine overlaps are far larger.
OVERLAP_TOL = 1e-12

CORE_COLUMNS = [
    "n", "k_n", "vertex_skipping", "s_n", "angle_str", "tension_state",
    "angle_rad", "angle_deg", "is_hex_resonance", "is_max_tense",
    "is_phase_shift", "is_multiple_placements", "is_minimally_tense",
    "uses_skipping",
]


# --------------------------------------------------------------------------- geometry
@lru_cache(maxsize=None)
def regular_polygon(n: int) -> tuple[tuple[float, float], ...]:
    """Vertices of the regular n-gon with circumradius 1, counter-clockwise."""
    if n < 3:
        raise ValueError("a polygon needs n >= 3 vertices")
    return tuple((math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
                 for i in range(n))


def neighbour(n: int, edge: int) -> Polygon:
    """Reflection of the central n-gon across its edge ``edge`` (edge i joins vertex i and i+1)."""
    verts = regular_polygon(n)
    (ax, ay), (bx, by) = verts[edge % n], verts[(edge + 1) % n]
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy

    def reflect(p: tuple[float, float]) -> tuple[float, float]:
        t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2
        fx, fy = ax + t * dx, ay + t * dy          # foot of the perpendicular
        return 2 * fx - p[0], 2 * fy - p[1]

    return Polygon([reflect(p) for p in verts])


def overlap_area(n: int, spacing: int) -> float:
    """Overlap area of the neighbours attached at edge 0 and edge ``spacing`` (circumradius 1)."""
    return neighbour(n, 0).intersection(neighbour(n, spacing)).area


def min_edge_spacing(n: int, tol: float = OVERLAP_TOL) -> int:
    """Smallest edge spacing m >= 1 at which the neighbours on edge 0 and edge m do not overlap."""
    base = neighbour(n, 0)
    for m in range(1, n):
        if base.intersection(neighbour(n, m)).area <= tol:
            return m
    return n


# --------------------------------------------------------------------------- solution
@dataclass(frozen=True)
class Solution:
    n: int
    spacing: int          # minimum non-overlapping edge spacing
    k: int                # conjoinability: neighbours that fit
    s: int                # vertex skipping: untouched vertices between neighbours
    overlap_below: float  # overlap area at spacing-1 (confidence margin; 0.0 if spacing == 1)

    @property
    def slack(self) -> int:
        """Edges left over after placing k neighbours at the minimum spacing (n - k*spacing)."""
        return self.n - self.k * self.spacing


def solve(n: int) -> Solution:
    """Solve k(n), s(n) for one n by exact polygon intersection."""
    m = min_edge_spacing(n)
    below = overlap_area(n, m - 1) if m > 1 else 0.0
    return Solution(n=n, spacing=m, k=n // m, s=max(0, m - 2), overlap_below=below)


def k_closed(n: int) -> int:
    """Closed form k(n) = floor(n / ceil(n/6))  (equals n for n <= 6)."""
    return n // math.ceil(n / 6)


def s_closed(n: int) -> int:
    """Closed form s(n) = max(0, ceil(n/6) - 2)."""
    return max(0, math.ceil(n / 6) - 2)


def arrangement(n: int) -> list[int]:
    """One valid arrangement: k edge spacings (each >= the minimum) that sum to n.

    The slack is spread as evenly as possible.  This is *one* placement, not a
    count of all placements.  Untouched vertices in gap i = spacing_i - 2.
    """
    sol = solve(n)
    spacings = [sol.spacing] * sol.k
    for i in range(sol.slack):
        spacings[i % sol.k] += 1
    return spacings


# --------------------------------------------------------------------------- verification
def _solve_tuple(n: int) -> tuple[int, int, int]:
    s = solve(n)
    return n, s.k, s.s


def verify(n_max: int = 400, n_min: int = 3, workers: int | None = None) -> list[int]:
    """Return every n in [n_min, n_max] where the exact solver disagrees with the closed forms."""
    ns = range(n_min, n_max + 1)
    if workers == 1:
        results = [_solve_tuple(n) for n in ns]
    else:
        with Pool(workers) as pool:
            results = pool.map(_solve_tuple, ns)
    return [n for n, k, s in results if (k, s) != (k_closed(n), s_closed(n))]


# --------------------------------------------------------------------------- table
def build_table(n_min: int = 3, n_max: int = 400,
                existing: pd.DataFrame | None = None,
                workers: int | None = None) -> pd.DataFrame:
    """Build the conjoinability table for n_min..n_max in the 14-column research schema.

    k_n, s_n, vertex_skipping and uses_skipping always come from the exact solver.
    If ``existing`` is given, its angle_str / tension_state / flag columns are kept
    for the n values it already has (missing columns are tolerated).  New n values,
    and rows already marked "Not assessed", get tension_state = "Not assessed" and
    blank tension flags.
    """
    ns = list(range(n_min, n_max + 1))
    if workers == 1:
        sols = {n: solve(n) for n in ns}
    else:
        with Pool(workers) as pool:
            sols = dict(zip(ns, pool.map(solve, ns)))

    old = {} if existing is None else existing.set_index("n").to_dict("index")
    rows = []
    for n in ns:
        sol, prev = sols[n], old.get(n)
        angle = prev.get("angle_str") if prev else None
        if not isinstance(angle, str) or not angle:
            angle = f"{n - 2}\u03c0/{n}"
        tension = prev.get("tension_state") if prev else None
        if not isinstance(tension, str) or not tension.strip():
            tension = "Not assessed"
        keep_flags = prev is not None and tension.strip().lower() != "not assessed"
        row = {
            "n": n, "k_n": sol.k,
            "vertex_skipping": "Yes" if sol.s > 0 else "No", "s_n": sol.s,
            "angle_str": angle, "tension_state": tension,
            "angle_rad": (n - 2) * math.pi / n, "angle_deg": (n - 2) * 180.0 / n,
            "is_hex_resonance": sol.k == 6,
            "uses_skipping": sol.s > 0,
        }
        for col in ("is_max_tense", "is_phase_shift", "is_multiple_placements", "is_minimally_tense"):
            row[col] = prev.get(col, np.nan) if keep_flags else np.nan
        rows.append(row)
    return pd.DataFrame(rows)[CORE_COLUMNS]


# --------------------------------------------------------------------------- CLI
def _cmd_solve(args: argparse.Namespace) -> int:
    sol = solve(args.n)
    print(f"n = {sol.n}: min edge spacing = {sol.spacing}, k(n) = {sol.k}, s(n) = {sol.s}, "
          f"slack = {sol.slack}")
    print(f"closed forms: k = {k_closed(args.n)}, s = {s_closed(args.n)}")
    print(f"one arrangement (edge spacings): {arrangement(args.n)}")
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    bad = verify(args.n_max, args.n_min, args.workers)
    if bad:
        print(f"MISMATCH between exact solver and closed forms at n = {bad}")
        return 1
    print(f"exact solver == closed forms for every n in {args.n_min}..{args.n_max}")
    return 0


def _cmd_table(args: argparse.Namespace) -> int:
    existing = pd.read_csv(args.existing) if args.existing else None
    table = build_table(args.n_min, args.n_max, existing, args.workers)
    table.to_csv(args.out, index=False)
    print(f"wrote {len(table)} rows (n = {args.n_min}..{args.n_max}) to {args.out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Exact geometric solver for k(n) and s(n).")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("solve", help="solve one n")
    a.add_argument("n", type=int); a.set_defaults(func=_cmd_solve)

    b = sub.add_parser("verify", help="check exact solver against the closed forms")
    b.add_argument("--n-min", type=int, default=3); b.add_argument("--n-max", type=int, default=400)
    b.add_argument("--workers", type=int, default=None); b.set_defaults(func=_cmd_verify)

    c = sub.add_parser("table", help="write the conjoinability table as CSV")
    c.add_argument("--n-min", type=int, default=3); c.add_argument("--n-max", type=int, default=400)
    c.add_argument("--existing", help="existing CSV whose tension labels should be kept")
    c.add_argument("--out", required=True); c.add_argument("--workers", type=int, default=None)
    c.set_defaults(func=_cmd_table)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())