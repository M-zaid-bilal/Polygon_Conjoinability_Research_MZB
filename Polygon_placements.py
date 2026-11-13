"""
Polygon_placements.py - ALL valid placements of neighbours around a central regular n-gon
Muhammad Zaid Bilal | Polygon Conjoinability Research

Builds on Polygon_solver.py (which gives k(n) and s(n)); this script answers the bigger
question: *which* sets of neighbours are valid, how many are there, and what do they look like?

Definitions
-----------
Central polygon: a regular n-gon with edges numbered 0..n-1 (edge i joins vertex i and i+1).
Neighbour on edge e: the reflection of the central polygon across edge e.
Placement: a set of edges that each carry a neighbour, such that no two neighbours overlap
(touching in a point or along the shared edge is allowed).

What counts as valid (confirmed against the GeoGebra drawings 25_GON and N_36_perfect)
-------------------------------------------------------------------------------------
Overlap on top of another polygon is NOT allowed; touching IS allowed.  Two kinds of valid
placement appear:

    open          neighbours stay apart from each other             (e.g. the 25-gon, k = 5)
    perfect ring  every neighbour shares an edge with the next one,  (e.g. the 36-gon, k = 6)
                  so the ring closes exactly; this happens only when 6 divides n

Key fact (checked by exact polygon intersection, see ``check_conflict_structure``)
-------------------------------------------------------------------------------
Two neighbours overlap exactly when their edges are closer than m = min_gap(n) around the
polygon (cyclic distance d < m), where m = ceil(n/6) for n >= 7 (m = 1 for n <= 6).  Hence

    a set of t edges is a valid placement  <=>  consecutive chosen edges are >= m apart.

Writing the t cyclic gaps as g_1..g_t (each >= m, sum = n):

    * untouched central vertices in gap i = max(0, g_i - 2)       (g_i = 1: a shared vertex)
    * the placement is *maximal* (nothing more fits) iff every gap < 2m
    * the largest placement has t = k(n) neighbours; its slack is n - k*m

Tight chains with BA fixed (the placements counted in the research)
-------------------------------------------------------------------
Fix one neighbour on edge 0 (called BA).  A *tight chain* has every gap equal to m (the "4 skipping"
for n = 34) except one gap, the *pocket*, which takes all the slack (m + slack).  Walking from BA
you meet `ahead` tight neighbours before the pocket and `behind` the other way round
(ahead + behind = size - 1).  Mirror images (about BA's axis) are the same placement, so
(ahead, behind) = (4, 0), (3, 1), (2, 2) for n = 34 are THREE placements.  In general a largest
tight chain has ceil(k/2) placements when slack > 0, and exactly one (the perfect ring) when slack = 0.

Counting (exact, closed form, no enumeration needed)
----------------------------------------------------
    labelled placements of size t       n/t * C(n - t(m-1) - 1, t - 1)
    up to rotation (necklaces)          Burnside over the t rotations
    up to rotation + reflection         Burnside over the dihedral group of order 2t

Enumeration is lazy (``iter_placements``), so you can browse huge spaces with ``limit``.

Command line
------------
    python Polygon_placements.py count 34                       # counts for every size
    python Polygon_placements.py list  34 --size 5 --symmetry dihedral --limit 20
    python Polygon_placements.py chains 34                      # tight chains with BA fixed: 3 placements
    python Polygon_placements.py check --n-max 120              # re-verify the key fact geometrically

Requires: pandas, shapely (via Polygon_solver)
"""
from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterator

import pandas as pd
from shapely.geometry import Point, Polygon

try:                                   # saved as Polygon_solver.py (also accept the lowercase name)
    import Polygon_solver as ps
except ModuleNotFoundError:
    try:
        import polygon_solver as ps
    except ModuleNotFoundError:
        raise ImportError("Polygon_solver.py must be in the same folder as Polygon_placements.py") from None


__all__ = [
    "Placement", "contact_kind", "min_gap", "max_size", "is_valid", "verify_placement_geometry",
    "conflict_distances", "check_conflict_structure",
    "ChainPlacement", "chain_placements", "count_chain", "contact_gap", "tension", "sawtooth_limit",
    "count_labelled", "count_classes", "count_by_size",
    "iter_placements", "list_placements", "to_dataframe",
]

SYMMETRIES = ("rotation", "dihedral", "none")


# --------------------------------------------------------------------------- basics
@lru_cache(maxsize=None)
def min_gap(n: int) -> int:
    """Smallest edge spacing m at which two neighbours do not overlap (1 for n <= 6)."""
    return ps.min_edge_spacing(n)


def max_size(n: int) -> int:
    """Largest placement size = k(n)."""
    return n // min_gap(n)


@lru_cache(maxsize=None)
def contact_kind(n: int, gap: int) -> str:
    """How two neighbours whose edges are `gap` apart relate: "overlap" (invalid), "touching"
    (they share a point or an edge) or "open" (a gap between them).  Exact geometry, cached."""
    d = min(gap, n - gap)
    a, b = ps.neighbour(n, 0), ps.neighbour(n, d)
    if a.intersection(b).area > ps.OVERLAP_TOL:
        return "overlap"
    return "touching" if a.distance(b) <= 1e-9 else "open"


@dataclass(frozen=True)
class Placement:
    n: int
    edges: tuple[int, ...]     # sorted edge indices that carry a neighbour
    gaps: tuple[int, ...]      # gaps[i] = cyclic distance from edges[i] to the next chosen edge

    @property
    def size(self) -> int:
        return len(self.edges)

    @property
    def untouched(self) -> tuple[int, ...]:
        """Untouched central vertices in each gap (a gap of 1 is a shared vertex, counted as 0)."""
        return tuple(max(0, g - 2) for g in self.gaps)

    @property
    def contacts(self) -> tuple[str, ...]:
        """For every gap: "touching" or "open" (empty for a single neighbour)."""
        return tuple(contact_kind(self.n, g) for g in self.gaps) if self.size >= 2 else ()

    @property
    def kind(self) -> str:
        """"perfect ring" (every neighbour touches the next), "open", "partly touching" or "single"."""
        if self.size == 1:
            return "single"
        c = set(self.contacts)
        return "perfect ring" if c == {"touching"} else "open" if c == {"open"} else "partly touching"

    @property
    def maximal(self) -> bool:
        """True if no further neighbour can be added."""
        return all(g < 2 * min_gap(self.n) for g in self.gaps)


def _make(n: int, edges: list[int] | tuple[int, ...]) -> Placement:
    e = tuple(sorted(edges))
    gaps = tuple((e[(i + 1) % len(e)] - e[i]) % n or n for i in range(len(e)))
    return Placement(n, e, gaps)


def is_valid(n: int, edges) -> bool:
    """Distance rule: distinct edges, every pair at cyclic distance >= min_gap(n)."""
    edges = sorted(set(int(e) % n for e in edges))
    m = min_gap(n)
    for i in range(len(edges)):
        for j in range(i + 1, len(edges)):
            d = edges[j] - edges[i]
            if min(d, n - d) < m:
                return False
    return True


def verify_placement_geometry(n: int, edges, tol: float = ps.OVERLAP_TOL) -> bool:
    """Independent check: build every neighbour and test all pairs by exact polygon intersection."""
    polys = [ps.neighbour(n, int(e)) for e in sorted(set(edges))]
    return all(polys[i].intersection(polys[j]).area <= tol
               for i in range(len(polys)) for j in range(i + 1, len(polys)))


def conflict_distances(n: int) -> set[int]:
    """Cyclic edge distances d (1..n//2) at which two neighbours overlap, by exact geometry."""
    return {d for d in range(1, n // 2 + 1) if ps.overlap_area(n, d) > ps.OVERLAP_TOL}


def check_conflict_structure(n: int) -> bool:
    """True if neighbours overlap exactly for d < min_gap(n) and never for larger d."""
    m = min_gap(n)
    return conflict_distances(n) == {d for d in range(1, n // 2 + 1) if d < m}


# --------------------------------------------------------------------------- counting
def count_labelled(n: int, t: int) -> int:
    """Number of valid placements of exactly t neighbours (edges labelled, nothing identified)."""
    if t == 0:
        return 1
    m = min_gap(n)
    if t < 0 or n < t * m:
        return 0
    num = n * math.comb(n - t * (m - 1) - 1, t - 1)
    assert num % t == 0
    return num // t


def _solutions(n: int, a: int, b: int, m: int) -> int:
    """# of (x_1..x_a, y_1..y_b), all >= m, with sum(x) + 2*sum(y) = n."""
    if a == 0 and b == 0:
        return 1 if n == 0 else 0
    if b == 0:
        return math.comb(n - a * (m - 1) - 1, a - 1) if n >= a * m else 0
    total = 0
    for sy in range(b * m, n // 2 + 1):
        r = n - 2 * sy
        wy = math.comb(sy - b * (m - 1) - 1, b - 1)
        if a == 0:
            if r == 0:
                total += wy
        elif r >= a * m:
            total += wy * math.comb(r - a * (m - 1) - 1, a - 1)
    return total


def count_classes(n: int, t: int) -> tuple[int, int]:
    """(# placements up to rotation, # up to rotation and reflection) of size t, by Burnside."""
    if t == 0:
        return 1, 1
    m = min_gap(n)
    if t < 0 or n < t * m:
        return 0, 0
    rot_fixed = 0
    for r in range(t):
        g = math.gcd(r, t)
        reps = t // g
        if n % reps == 0:
            s = n // reps
            if s >= g * m:
                rot_fixed += math.comb(s - g * (m - 1) - 1, g - 1)
    if t % 2 == 1:
        refl_fixed = t * _solutions(n, 1, (t - 1) // 2, m)
    else:
        refl_fixed = (t // 2) * (_solutions(n, 2, (t - 2) // 2, m) + _solutions(n, 0, t // 2, m))
    assert rot_fixed % t == 0 and (rot_fixed + refl_fixed) % (2 * t) == 0
    return rot_fixed // t, (rot_fixed + refl_fixed) // (2 * t)


def count_by_size(n: int) -> pd.DataFrame:
    """Counts for every placement size 1..k(n)."""
    rows = []
    for t in range(1, max_size(n) + 1):
        rot, dih = count_classes(n, t)
        rows.append({"size": t, "labelled": count_labelled(n, t),
                     "up_to_rotation": rot, "up_to_rotation_and_reflection": dih})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- tension
def _difference_body(n: int) -> Polygon:
    """D = P - P for the unit-circumradius regular n-gon P: 2P for even n, a regular 2n-gon for odd n."""
    if n % 2 == 0:
        return Polygon([(2 * math.cos(2 * math.pi * k / n), 2 * math.sin(2 * math.pi * k / n)) for k in range(n)])
    rho = 2 * math.cos(math.pi / (2 * n))
    return Polygon([(rho * math.cos((j + 0.5) * math.pi / n), rho * math.sin((j + 0.5) * math.pi / n))
                    for j in range(2 * n)])


@lru_cache(maxsize=None)
def contact_gap(n: int) -> float:
    """Tension tau(n) of the tightest packing: the distance between two neighbours whose edges are
    m(n) apart, in units of the polygon's side.  It is 0 for n <= 6 and exactly when 6 divides n
    for n >= 7 (report, Thm 7.1(i)-(ii)).  Closed form via the difference body D = P - P: for
    translates of a convex body, dist(x+K, y+K) = dist(y-x, K-K)."""
    m = min_gap(n)
    a = math.cos(math.pi / n)
    p0, pm = math.pi / n, 2 * math.pi * (m + 0.5) / n
    c = (2 * a * (math.cos(pm) - math.cos(p0)), 2 * a * (math.sin(pm) - math.sin(p0)))
    return max(0.0, _difference_body(n).distance(Point(c)) / (2 * math.sin(math.pi / n)))


tension = contact_gap          # the name used in the report: tau(n)


def sawtooth_limit(n: int) -> float:
    """Limit profile of the tension: (sqrt(3)/6) * ((-n) mod 6).  For n >= 7, 6 not dividing n,
    |tension(n) - limit| <= ((kappa^2)/2 + 1) * pi / n with kappa = (6 - n mod 6)/6 (report, Thm 7.1(iii))."""
    return math.sqrt(3) / 6 * ((-n) % 6)


# --------------------------------------------------------------------------- tight chains, BA fixed
@dataclass(frozen=True)
class ChainPlacement:
    """A tight-chain placement with BA (edge 0) occupied."""
    placement: Placement
    ahead: int      # tight neighbours met going one way from BA before the pocket
    behind: int     # tight neighbours going the other way

    @property
    def label(self) -> str:
        return "ring" if self.placement.kind == "perfect ring" else f"{self.ahead}+{self.behind}"

    @property
    def pocket_untouched(self) -> int:
        """Untouched central vertices in the pocket (the one gap larger than m; m-2 if there is none)."""
        return max(self.placement.untouched)


def chain_placements(n: int, size: int | None = None, mirror: bool = True) -> list[ChainPlacement]:
    """All tight-chain placements of `size` neighbours (default: the maximum k) with BA fixed on edge 0.

    mirror=True  : a placement and its mirror image about BA's axis are one placement (ahead >= behind)
    mirror=False : both are listed
    """
    t = max_size(n) if size is None else size
    m = min_gap(n)
    if t < 1 or n < t * m:
        return []
    slack = n - t * m
    if t == 1 or slack == 0:                       # a single neighbour, or the closed perfect ring
        positions = [t - 1]
    elif mirror:
        positions = list(range(math.ceil((t - 1) / 2), t))
    else:
        positions = list(range(t))
    out = []
    for big in positions:                          # `big` = index of the pocket gap, counted from BA
        gaps = [m] * t
        gaps[big] = n - (t - 1) * m                # pocket takes all the slack (= n when t == 1)
        edges = [0]
        for g in gaps[:-1]:
            edges.append(edges[-1] + g)
        ahead, behind = (big, t - 1 - big) if t > 1 and slack > 0 else (t - 1, 0)
        out.append(ChainPlacement(_make(n, edges), ahead, behind))
    return out


def count_chain(n: int, size: int | None = None, mirror: bool = True) -> int:
    """Number of tight-chain placements with BA fixed (closed form)."""
    t = max_size(n) if size is None else size
    m = min_gap(n)
    if t < 1 or n < t * m:
        return 0
    if t == 1 or n == t * m:
        return 1
    return (t + 1) // 2 if mirror else t


# --------------------------------------------------------------------------- enumeration
def _compositions(total: int, parts: int, minimum: int) -> Iterator[tuple[int, ...]]:
    """All tuples of `parts` integers >= minimum summing to total, in lexicographic order."""
    if parts == 1:
        if total >= minimum:
            yield (total,)
        return
    for first in range(minimum, total - (parts - 1) * minimum + 1):
        for rest in _compositions(total - first, parts - 1, minimum):
            yield (first,) + rest


def _is_canonical(seq: tuple[int, ...], dihedral: bool) -> bool:
    t = len(seq)
    if any(seq > seq[i:] + seq[:i] for i in range(1, t)):
        return False
    if dihedral:
        rev = seq[::-1]
        if any(seq > rev[i:] + rev[:i] for i in range(t)):
            return False
    return True


def iter_placements(n: int, size: int | None = None, symmetry: str = "rotation",
                    limit: int | None = None) -> Iterator[Placement]:
    """Lazily yield valid placements of `size` neighbours (default: the maximum, k(n)).

    symmetry = "rotation"  one placement per rotation class (start at edge 0)
               "dihedral"  one per rotation + reflection class
               "none"      every labelled placement (can be huge - use `limit`)
    """
    if symmetry not in SYMMETRIES:
        raise ValueError(f"symmetry must be one of {SYMMETRIES}")
    t = max_size(n) if size is None else size
    m = min_gap(n)
    if t < 1 or n < t * m:
        return
    produced = 0
    seen: set[tuple[int, ...]] = set()
    for seq in _compositions(n, t, m):
        if not _is_canonical(seq, dihedral=(symmetry == "dihedral")):
            continue
        base = [0]
        for g in seq[:-1]:
            base.append(base[-1] + g)
        if symmetry == "none":
            seen.clear()                     # dedupe rotations of periodic sequences
            for r in range(n):
                edges = tuple(sorted((e + r) % n for e in base))
                if edges in seen:
                    continue
                seen.add(edges)
                yield _make(n, edges)
                produced += 1
                if limit is not None and produced >= limit:
                    return
        else:
            yield _make(n, base)
            produced += 1
            if limit is not None and produced >= limit:
                return


def list_placements(n: int, size: int | None = None, symmetry: str = "rotation",
                    limit: int | None = 50, order: str = "lexicographic",
                    sort_cap: int = 20000) -> list[Placement]:
    """Collect placements. order="balanced" lists the most even gap patterns first, but needs the
    whole class list, so it is used only when there are at most `sort_cap` of them (otherwise it
    silently falls back to lexicographic order)."""
    t = max_size(n) if size is None else size
    if order == "balanced":
        rot, dih = count_classes(n, t)
        total = {"rotation": rot, "dihedral": dih, "none": count_labelled(n, t)}[symmetry]
        if total <= sort_cap:
            allp = list(iter_placements(n, t, symmetry))
            allp.sort(key=lambda p: (max(p.gaps) - min(p.gaps), p.gaps, p.edges))
            return allp if limit is None else allp[:limit]
    return list(iter_placements(n, t, symmetry, limit))


def to_dataframe(placements: list[Placement]) -> pd.DataFrame:
    """Tabular view: one row per placement."""
    return pd.DataFrame([{
        "n": p.n, "size": p.size, "kind": p.kind,
        "gaps": "-".join(map(str, p.gaps)),
        "untouched": "-".join(map(str, p.untouched)),
        "edges": " ".join(map(str, p.edges)),
        "maximal": p.maximal,
    } for p in placements])


# --------------------------------------------------------------------------- CLI
def _cmd_count(a: argparse.Namespace) -> int:
    m, k = min_gap(a.n), max_size(a.n)
    print(f"n = {a.n}: minimum gap m = {m}, largest placement k = {k}, slack = {a.n - k * m}")
    print(count_by_size(a.n).to_string(index=False))
    return 0


def _cmd_list(a: argparse.Namespace) -> int:
    ps_ = list_placements(a.n, a.size, a.symmetry, a.limit, a.order)
    if not ps_:
        print("no valid placement of that size")
        return 1
    print(to_dataframe(ps_).to_string(index=False))
    return 0


def _cmd_chains(a: argparse.Namespace) -> int:
    chains = chain_placements(a.n, a.size, mirror=not a.no_mirror)
    if not chains:
        print("no tight chain of that size")
        return 1
    print(f"n = {a.n}: minimum gap m = {min_gap(a.n)}, tight chains with BA fixed"
          f" ({'mirror images identified' if not a.no_mirror else 'mirror images listed separately'}): {len(chains)}")
    df = to_dataframe([c.placement for c in chains])
    df.insert(2, "ahead+behind", [c.label for c in chains])
    print(df.to_string(index=False))
    return 0


def _cmd_check(a: argparse.Namespace) -> int:
    bad = [n for n in range(a.n_min, a.n_max + 1) if not check_conflict_structure(n)]
    if bad:
        print(f"conflict structure FAILS at n = {bad}")
        return 1
    print(f"neighbours overlap exactly when edge distance < min_gap, for every n in {a.n_min}..{a.n_max}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="All valid placements around a central regular n-gon.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("count", help="how many placements of each size")
    c.add_argument("n", type=int); c.set_defaults(func=_cmd_count)

    l = sub.add_parser("list", help="list placements")
    l.add_argument("n", type=int)
    l.add_argument("--size", type=int, default=None, help="number of neighbours (default: maximum)")
    l.add_argument("--symmetry", choices=SYMMETRIES, default="rotation")
    l.add_argument("--limit", type=int, default=30)
    l.add_argument("--order", choices=("lexicographic", "balanced"), default="balanced")
    l.set_defaults(func=_cmd_list)

    h = sub.add_parser("chains", help="tight-chain placements with BA (edge 0) fixed")
    h.add_argument("n", type=int); h.add_argument("--size", type=int, default=None)
    h.add_argument("--no-mirror", action="store_true", help="list mirror images separately")
    h.set_defaults(func=_cmd_chains)

    k = sub.add_parser("check", help="re-verify the overlap structure by exact geometry")
    k.add_argument("--n-min", type=int, default=3); k.add_argument("--n-max", type=int, default=120)
    k.set_defaults(func=_cmd_check)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())