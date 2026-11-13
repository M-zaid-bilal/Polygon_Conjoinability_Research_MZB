"""Tests for Polygon_placements.  Run:  pytest test_polygon_placements.py -q

The brute-force tests build the conflict matrix from REAL polygon intersections for every pair of
edges and enumerate every subset, so they do not depend on the gap formulas being tested.
"""
import itertools
import math
import random

import pytest

try:
    import Polygon_solver as ps
except ModuleNotFoundError:
    import polygon_solver as ps
try:
    import Polygon_placements as pp
except ModuleNotFoundError:
    import polygon_placements as pp


# --------------------------------------------------------------------------- brute force helpers
def conflict_matrix(n):
    polys = [ps.neighbour(n, e) for e in range(n)]
    return [[i != j and polys[i].intersection(polys[j]).area > ps.OVERLAP_TOL for j in range(n)]
            for i in range(n)]


def brute_force_valid_sets(n):
    """Every non-empty set of edges whose neighbours pairwise do not overlap (real geometry)."""
    bad = conflict_matrix(n)
    out = []
    for t in range(1, n + 1):
        for combo in itertools.combinations(range(n), t):
            if all(not bad[a][b] for a, b in itertools.combinations(combo, 2)):
                out.append(frozenset(combo))
    return out


def canon(subset, n, dihedral):
    """Canonical representative of an edge set under rotation (and reflection)."""
    best = None
    for r in range(n):
        for sign in ((1, -1) if dihedral else (1,)):
            img = tuple(sorted((sign * e + r) % n for e in subset))
            best = img if best is None or img < best else best
    return best


# --------------------------------------------------------------------------- geometry / structure
def test_conflict_structure_matches_gap_rule():
    for n in range(3, 61):
        assert pp.check_conflict_structure(n), n


@pytest.mark.parametrize("n", range(3, 13))
def test_all_valid_placements_equal_brute_force(n):
    brute = brute_force_valid_sets(n)
    for t in range(1, pp.max_size(n) + 1):
        want = {s for s in brute if len(s) == t}
        got = {frozenset(p.edges) for p in pp.iter_placements(n, t, "none")}
        assert got == want, (n, t)
    assert max(len(s) for s in brute) == pp.max_size(n)            # largest size is k(n)
    assert not any(len(s) > pp.max_size(n) for s in brute)


@pytest.mark.parametrize("n", range(3, 13))
def test_counts_and_classes_equal_brute_force(n):
    brute = brute_force_valid_sets(n)
    for t in range(1, pp.max_size(n) + 1):
        sets = [s for s in brute if len(s) == t]
        rot = len({canon(s, n, False) for s in sets})
        dih = len({canon(s, n, True) for s in sets})
        assert pp.count_labelled(n, t) == len(sets), (n, t)
        assert pp.count_classes(n, t) == (rot, dih), (n, t)


@pytest.mark.parametrize("n", [13, 14, 15, 16])
def test_counts_equal_brute_force_slightly_larger(n):
    brute = brute_force_valid_sets(n)
    for t in range(1, pp.max_size(n) + 1):
        sets = [s for s in brute if len(s) == t]
        assert pp.count_labelled(n, t) == len(sets)
        assert pp.count_classes(n, t) == (len({canon(s, n, False) for s in sets}),
                                          len({canon(s, n, True) for s in sets}))


def test_maximal_flag_equals_brute_force():
    for n in range(3, 13):
        bad = conflict_matrix(n)
        for t in range(1, pp.max_size(n) + 1):
            for p in pp.iter_placements(n, t, "none"):
                can_add = any(e not in p.edges and all(not bad[e][x] for x in p.edges) for e in range(n))
                assert p.maximal == (not can_add), (n, p.edges)


# --------------------------------------------------------------------------- enumeration vs counting
@pytest.mark.parametrize("n", [7, 13, 19, 25, 30, 31, 34, 37, 42])
def test_enumeration_matches_closed_form_counts(n):
    for t in range(1, pp.max_size(n) + 1):
        rot, dih = pp.count_classes(n, t)
        assert sum(1 for _ in pp.iter_placements(n, t, "rotation")) == rot
        assert sum(1 for _ in pp.iter_placements(n, t, "dihedral")) == dih
        if pp.count_labelled(n, t) <= 20000:
            assert sum(1 for _ in pp.iter_placements(n, t, "none")) == pp.count_labelled(n, t)


def test_every_enumerated_placement_is_geometrically_valid():
    for n in (7, 19, 25, 34, 41, 55):
        for p in pp.list_placements(n, None, "rotation", limit=15):
            assert sum(p.gaps) == n
            assert pp.is_valid(n, p.edges)
            assert pp.verify_placement_geometry(n, p.edges)


def test_distance_rule_agrees_with_geometry_on_random_sets():
    rnd = random.Random(7)
    for n in (20, 25, 31):
        bad = conflict_matrix(n)
        for _ in range(300):
            t = rnd.randint(1, 8)
            edges = rnd.sample(range(n), t)
            geom = all(not bad[a][b] for a, b in itertools.combinations(edges, 2))
            assert pp.is_valid(n, edges) == geom


def test_one_edge_too_close_is_invalid():
    n = 34                                  # min gap 6
    assert pp.is_valid(n, [0, 6, 12, 18, 24])
    assert not pp.is_valid(n, [0, 5, 12, 18, 24])
    assert not pp.verify_placement_geometry(n, [0, 5, 12, 18, 24])


# --------------------------------------------------------------------------- known values and API
def test_known_values():
    assert pp.max_size(25) == 5 and pp.min_gap(25) == 5
    assert pp.count_labelled(25, 5) == 5                          # only the 5 rotations of (5,5,5,5,5)
    assert pp.count_classes(25, 5) == (1, 1)
    assert pp.count_classes(34, 5) == (sum(1 for _ in pp.iter_placements(34, 5, 'rotation')),
                                       sum(1 for _ in pp.iter_placements(34, 5, 'dihedral')))
    first = list(pp.iter_placements(25, 5, "rotation"))
    assert len(first) == 1 and first[0].gaps == (5, 5, 5, 5, 5) and first[0].untouched == (3,) * 5
    assert pp.count_labelled(174, 6) == 29                         # only rotations of (29,)*6 -> 174/6
    assert pp.count_labelled(12, 6) == 2                           # hexagonal resonance: 2 alternating sets


def test_hexagonal_resonance_has_few_placements():
    for m in range(1, 40):
        n = 6 * m
        assert pp.count_classes(n, 6) == (1, 1)                    # always one uniform pattern up to symmetry


def test_largest_placement_uses_the_solver_k():
    for n in range(3, 120):
        assert pp.max_size(n) == ps.solve(n).k
        assert pp.count_labelled(n, pp.max_size(n)) > 0
        assert pp.count_labelled(n, pp.max_size(n) + 1) == 0


def test_solver_arrangement_is_one_of_the_placements():
    for n in (13, 25, 34, 55, 100):
        gaps = ps.arrangement(n)
        edges = [sum(gaps[:i]) for i in range(len(gaps))]
        assert pp.is_valid(n, edges) and pp.verify_placement_geometry(n, edges)
        assert len(gaps) == pp.max_size(n)


def test_limit_and_order():
    n = 55
    assert len(pp.list_placements(n, None, "rotation", limit=5)) == 5
    bal = pp.list_placements(n, None, "rotation", limit=3, order="balanced")
    spread = [max(p.gaps) - min(p.gaps) for p in bal]
    assert spread == sorted(spread) and spread[0] <= 1             # most even pattern first
    lex = pp.list_placements(n, None, "rotation", limit=3, order="lexicographic")
    assert [p.gaps for p in lex] == sorted(p.gaps for p in lex)
    huge = pp.list_placements(400, None, "rotation", limit=4, order="balanced")   # too many to sort: falls back
    assert len(huge) == 4


def test_count_by_size_and_dataframe_schema():
    df = pp.count_by_size(34)
    assert list(df.columns) == ["size", "labelled", "up_to_rotation", "up_to_rotation_and_reflection"]
    assert list(df["size"]) == [1, 2, 3, 4, 5]
    table = pp.to_dataframe(pp.list_placements(34, 5, "dihedral", limit=3))
    assert list(table.columns) == ["n", "size", "kind", "gaps", "untouched", "edges", "maximal"]
    assert table["maximal"].all()                                   # largest placements are always maximal


def test_invalid_arguments():
    assert list(pp.iter_placements(25, 6)) == []                   # 6 neighbours do not fit
    assert list(pp.iter_placements(25, 0)) == []
    with pytest.raises(ValueError):
        list(pp.iter_placements(25, 5, "sideways"))


# --------------------------------------------------------------------------- the two accepted kinds
def test_36_gon_perfect_ring_like_the_geogebra_drawing():
    """N_36_perfect.ggb: neighbours on edges 0,6,12,18,24,30; adjacent ones share an edge; no overlap."""
    edges = [0, 6, 12, 18, 24, 30]
    assert pp.is_valid(36, edges) and pp.verify_placement_geometry(36, edges)
    p = pp._make(36, edges)
    assert p.gaps == (6,) * 6 and p.kind == "perfect ring" and p.maximal
    assert p.untouched == (4,) * 6                                  # s(36) = 4
    assert pp.contact_kind(36, 6) == "touching"


def test_25_gon_open_arrangement_like_the_geogebra_drawing():
    """25_GON.ggb: neighbours on edges 0,5,10,15,20; they do not touch each other."""
    edges = [0, 5, 10, 15, 20]
    assert pp.is_valid(25, edges) and pp.verify_placement_geometry(25, edges)
    p = pp._make(25, edges)
    assert p.kind == "open" and p.untouched == (3,) * 5
    assert pp.contact_kind(25, 5) == "open"


def test_overlap_on_top_is_rejected():
    assert pp.contact_kind(36, 5) == "overlap" and not pp.is_valid(36, [0, 5])
    assert pp.contact_kind(25, 4) == "overlap" and not pp.is_valid(25, [0, 4])
    assert not pp.verify_placement_geometry(25, [0, 4])


def test_perfect_ring_exists_exactly_when_6_divides_n():
    for n in range(7, 121):
        kinds = {p.kind for p in pp.iter_placements(n, None, "rotation")}
        assert ("perfect ring" in kinds) == (n % 6 == 0), n
    for m in range(1, 21):                                          # and it is then the ONLY largest placement
        ps_ = list(pp.iter_placements(6 * m, 6, "rotation"))
        assert len(ps_) == 1 and ps_[0].kind == "perfect ring"


def test_partly_touching_example():
    p = pp._make(36, [0, 6, 12, 18, 24])                            # gaps 6,6,6,6,12
    assert p.gaps == (6, 6, 6, 6, 12) and p.kind == "partly touching"
    assert pp.verify_placement_geometry(36, p.edges)


# --------------------------------------------------------------------------- tight chains with BA fixed
def test_n34_has_three_chain_placements_including_both_uploaded_files():
    chains = pp.chain_placements(34)
    assert pp.count_chain(34) == len(chains) == 3
    assert sorted((c.ahead, c.behind) for c in chains) == [(2, 2), (3, 1), (4, 0)]
    edges = {c.placement.edges for c in chains}
    assert (0, 6, 12, 18, 24) in edges            # 34_placement_1.ggb  (4+0)
    assert (0, 6, 12, 18, 28) in edges            # 34_placement_2.ggb  (3+1)
    assert (0, 6, 12, 22, 28) in edges            # symmetric about BA  (2+2)
    for c in chains:
        assert 0 in c.placement.edges and c.placement.kind == "open"
        assert pp.is_valid(34, c.placement.edges) and pp.verify_placement_geometry(34, c.placement.edges)
        assert c.pocket_untouched == 8 and sorted(c.placement.gaps) == [6, 6, 6, 6, 10]


def test_chain_without_mirror_lists_both_orientations():
    plain = pp.chain_placements(34, mirror=False)
    assert len(plain) == pp.count_chain(34, mirror=False) == 5
    assert sorted((c.ahead, c.behind) for c in plain) == [(0, 4), (1, 3), (2, 2), (3, 1), (4, 0)]


def test_chain_placements_all_chain_and_closed_form_count():
    for n in range(3, 130):
        k, m = pp.max_size(n), pp.min_gap(n)
        slack = n - k * m
        for size in range(1, k + 1):
            s_ = n - size * m
            for mirror in (True, False):
                ch = pp.chain_placements(n, size, mirror)
                assert len(ch) == pp.count_chain(n, size, mirror), (n, size, mirror)
                for c in ch:
                    g = sorted(c.placement.gaps)
                    assert 0 in c.placement.edges and pp.is_valid(n, c.placement.edges)
                    assert g[:-1] == [m] * (size - 1) or size == 1       # all gaps tight but the pocket
                    assert c.ahead + c.behind == size - 1 or s_ == 0 or size == 1
        expected = 1 if slack == 0 else (k + 1) // 2
        assert pp.count_chain(n) == expected, n


def test_chain_placements_are_a_subset_of_all_anchored_placements():
    for n in (7, 13, 25, 34, 41):
        everything = {p.edges for p in pp.iter_placements(n, None, "none") if 0 in p.edges}
        for c in pp.chain_placements(n, mirror=False):
            assert c.placement.edges in everything


def test_perfect_ring_is_a_single_chain_placement():
    for m in range(1, 30):
        ch = pp.chain_placements(6 * m)
        assert len(ch) == 1 and ch[0].label == "ring"


def test_chain_counts_by_k():
    # slack > 0: k=3 -> 2, k=4 -> 2, k=5 -> 3
    assert pp.count_chain(7) == 2 and pp.count_chain(9) == 2 and pp.count_chain(34) == 3 and pp.count_chain(55) == 3
    assert pp.count_chain(36) == 1 and pp.count_chain(174) == 1


# --------------------------------------------------------------------------- tension: the contact gap
def test_contact_gap_equals_exact_polygon_distance():
    for n in range(3, 61):
        m = pp.min_gap(n)
        side = 2 * math.sin(math.pi / n)
        exact = ps.neighbour(n, 0).distance(ps.neighbour(n, m)) / side
        assert abs(pp.contact_gap(n) - exact) < 1e-9, n


def test_contact_gap_is_zero_exactly_at_the_resonances():
    for n in range(7, 301):
        assert (pp.contact_gap(n) < 1e-9) == (n % 6 == 0), n
    for n in range(3, 7):
        assert pp.contact_gap(n) < 1e-9                              # n <= 6: neighbours never separate


def test_contact_gap_converges_to_the_sawtooth():
    worst = max(abs(pp.contact_gap(n) - pp.sawtooth_limit(n)) * n for n in range(40, 601))
    assert worst < 2.6                                              # error is O(1/n): n*error stays bounded
    assert abs(pp.sawtooth_limit(37) - math.sqrt(3) / 6 * 5) < 1e-12 and pp.sawtooth_limit(36) == 0.0


def test_tension_explicit_bound_of_theorem_7_1_iii():
    """|tau - sqrt3*kappa| <= (kappa^2/2 + 1) u, with the intermediate bounds proved in the report."""
    for n in range(7, 601):
        if n % 6 == 0:
            continue
        r = n % 6
        kappa, u = (6 - r) / 6, math.pi / n
        tau = pp.tension(n)
        assert abs(tau - math.sqrt(3) * kappa) <= (kappa ** 2 / 2 + 1) * u, n
        a, ell, m = math.cos(u), 2 * math.sin(u), -(-n // 6)
        c = 4 * a * math.sin(math.pi * m / n)
        lam = (c - 2 * a) / ell                                   # Lambda_n of the report
        theta = (lam - (math.sqrt(3) * kappa - kappa ** 2 * u / 2)) / u ** 2
        assert -0.9 <= theta <= 0.26, (n, theta)
        assert -1e-9 <= lam - tau <= math.tan(u / 2) + 1e-9, n   # Step 1 of the proof


# =========================================================================== completeness: edge branches
def test_single_neighbour_and_empty_placement_edge_cases():
    p = pp._make(25, [0])
    assert p.size == 1 and p.kind == "single" and p.contacts == () and p.gaps == (25,)
    assert p.untouched == (23,) and pp.verify_placement_geometry(25, [0])
    assert pp.count_labelled(25, 0) == 1 and pp.count_classes(25, 0) == (1, 1)
    assert pp.count_labelled(25, 6) == 0 and pp.count_classes(25, 6) == (0, 0)      # six do not fit
    assert pp.count_classes(25, -1) == (0, 0) and pp.count_labelled(25, -1) == 0
    assert pp._solutions(0, 0, 0, 3) == 1 and pp._solutions(5, 0, 0, 3) == 0        # empty-sum branch


def test_conflict_distances_are_exactly_the_distances_below_the_minimal_spacing():
    assert pp.conflict_distances(25) == {1, 2, 3, 4}                                # m(25) = 5
    assert pp.conflict_distances(36) == {1, 2, 3, 4, 5}                             # m(36) = 6
    assert pp.conflict_distances(6) == set()                                        # m = 1: nothing conflicts
    for n in (7, 8, 13, 14, 19, 31):
        assert pp.conflict_distances(n) == set(range(1, pp.min_gap(n)))


def test_iteration_limits_in_every_symmetry_mode():
    for sym in ("rotation", "dihedral", "none"):
        got = list(pp.iter_placements(34, 5, sym, limit=3))
        assert len(got) == 3 and len({p.edges for p in got}) == 3, sym
    allnone = list(pp.iter_placements(25, 5, "none"))
    assert len(allnone) == 5 and len({p.edges for p in allnone}) == 5               # periodic ring: 5 rotations, no duplicates
    assert pp.list_placements(25, 5, "none", limit=None, order="balanced") == sorted(
        allnone, key=lambda p: (max(p.gaps) - min(p.gaps), p.gaps, p.edges))


def test_chain_placements_edge_cases():
    assert pp.chain_placements(25, 6) == [] and pp.chain_placements(25, 0) == []
    assert pp.count_chain(25, 6) == 0 and pp.count_chain(25, 0) == 0
    one = pp.chain_placements(25, 1)
    assert len(one) == 1 and one[0].placement.edges == (0,) and pp.count_chain(25, 1) == 1
    shorter = pp.chain_placements(34, 3)                                            # a chain of 3 with slack 34 - 18 = 16
    assert len(shorter) == pp.count_chain(34, 3) == 2
    assert all(c.placement.gaps and sorted(c.placement.gaps)[:2] == [6, 6] for c in shorter)
    assert all(pp.is_valid(34, c.placement.edges) for c in shorter)


def test_lowercase_module_name_fallback(tmp_path):
    """Polygon_placements imports Polygon_solver, and falls back to polygon_solver (lowercase)."""
    import pathlib, shutil, subprocess, sys
    shutil.copy(pathlib.Path(ps.__file__), tmp_path / "polygon_solver.py")          # only the lowercase name exists here
    shutil.copy(pathlib.Path(pp.__file__), tmp_path / "Polygon_placements.py")
    out = subprocess.run([sys.executable, "-c", "import Polygon_placements as p; print(p.ps.__name__, p.max_size(25))"],
                         cwd=tmp_path, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["polygon_solver", "5"]


# =========================================================================== completeness: command line
def test_cli_count(capsys):
    assert pp.main(["count", "34"]) == 0
    out = capsys.readouterr().out
    assert "minimum gap m = 6" in out and "largest placement k = 5" in out and "slack = 4" in out
    assert "476" in out and "1734" in out


def test_cli_list_and_empty_list(capsys):
    assert pp.main(["list", "34", "--size", "5", "--symmetry", "dihedral", "--limit", "3"]) == 0
    out = capsys.readouterr().out
    assert "gaps" in out and "open" in out and out.count("\n") >= 4
    assert pp.main(["list", "25", "--size", "6"]) == 1
    assert "no valid placement" in capsys.readouterr().out


def test_cli_chains(capsys):
    assert pp.main(["chains", "34"]) == 0
    out = capsys.readouterr().out
    assert "4+0" in out and "3+1" in out and "2+2" in out and "mirror images identified" in out
    assert pp.main(["chains", "34", "--no-mirror"]) == 0
    out = capsys.readouterr().out
    assert "0+4" in out and "1+3" in out and "listed separately" in out
    assert pp.main(["chains", "25", "--size", "6"]) == 1
    assert "no tight chain" in capsys.readouterr().out


def test_cli_check_success_failure_and_bad_arguments(capsys, monkeypatch):
    assert pp.main(["check", "--n-min", "7", "--n-max", "30"]) == 0
    assert "overlap exactly when edge distance < min_gap" in capsys.readouterr().out
    monkeypatch.setattr(pp, "check_conflict_structure", lambda n: n != 9)
    assert pp.main(["check", "--n-min", "7", "--n-max", "12"]) == 1
    assert "FAILS at n = [9]" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        pp.main([])                                                                 # a sub-command is required
    with pytest.raises(SystemExit):
        pp.main(["list", "34", "--symmetry", "sideways"])


# =========================================================================== completeness: theorems of the report
def _counts_poly(n, m):
    """Coefficients of F_{n,m}(x) from the counting formula (Theorem 5.1), independent of the geometry."""
    return [1] + [n * math.comb(n - t * (m - 1) - 1, t - 1) // t for t in range(1, n // m + 1)]


def _recurrence_poly(n, m):
    """p_n(x) from p_0 = m, p_j = 1 (0 < j < m), p_j = p_{j-1} + x p_{j-m}  (Theorem 6.1(c))."""
    def add(a, b):
        size = max(len(a), len(b))
        return [(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(size)]
    p = [[m]] + [[1] for _ in range(1, m)]
    for j in range(m, n + 1):
        p.append(add(p[j - 1], [0] + p[j - m]))
    out = p[n]
    while out and out[-1] == 0:
        out = out[:-1]
    return out


def test_theorem_6_1_generating_function_identity():
    for m in range(1, 9):
        for n in range(m, 70):
            assert _recurrence_poly(n, m) == _counts_poly(n, m), (n, m)
    import numpy as np                                                              # and with the actual roots
    x, m, n = 0.37, 5, 41
    roots = np.roots([1, -1] + [0] * (m - 2) + [-x])
    assert sum(r ** n for r in roots).real == pytest.approx(sum(c * x ** t for t, c in enumerate(_counts_poly(n, m))))


def test_theorem_6_1_for_m_equals_2_is_the_lucas_polynomial():
    assert _recurrence_poly(5, 2) == [1, 5, 5] == _counts_poly(5, 2)
    assert _recurrence_poly(4, 2) == [1, 4, 2] and _recurrence_poly(3, 2) == [1, 3]


def test_placement_polynomial_of_the_n_gon_and_corollary_6_2():
    assert _counts_poly(34, 6) == [1, 34, 391, 1734, 2431, 476]                     # P_34(x)
    table = pp.count_by_size(34)
    assert list(table["labelled"]) == [34, 391, 1734, 2431, 476]
    for n in range(7, 121):                                                         # module == formula, degree == k(n)
        poly = _counts_poly(n, pp.min_gap(n))
        assert len(poly) - 1 == pp.max_size(n)
        assert [1] + list(pp.count_by_size(n)["labelled"]) == poly
    for m in range(2, 11):                                                          # windows 6m-5 .. 6m
        for n in range(6 * m - 5, 6 * m + 1):
            assert pp.min_gap(n) == m
        assert pp.max_size(6 * m) == 6 and pp.count_labelled(6 * m, 6) == m
        assert all(pp.max_size(n) < 6 for n in range(6 * m - 5, 6 * m))


def test_burnside_worked_example_n34_t5():
    assert math.comb(8, 4) == 70 and 70 // 5 == 14                                  # rotations: F_0 = 70, others 0
    assert pp._solutions(34, 1, 2, 6) == 6 and 5 * 6 == 30                          # reflections
    assert (70 + 30) // 10 == 10
    assert pp.count_classes(34, 5) == (14, 10)


def test_corollary_4_4_values_of_the_slack():
    ceil6 = lambda n: -(-n // 6)
    sigma = lambda n: n - (n // ceil6(n)) * ceil6(n)
    nonmult = [n for n in range(7, 5001) if n % 6]
    assert [n for n in nonmult if sigma(n) == 0] == [8, 10, 15, 20, 25]
    assert [n for n in range(7, 5001) if sigma(n) == 1] == [7, 9, 11, 13, 16, 21, 26, 31]
    assert all(sigma(n) >= 2 for n in nonmult if n >= 32)
    assert all(sigma(n) == 0 for n in range(6, 5001, 6))
    for n in nonmult:                                                               # Theorem 4.2(c)
        q, r = divmod(n, 6)
        k = n // ceil6(n)
        assert k == 6 - -(-(6 - r) // (q + 1))
        if k == 5:
            assert sigma(n) == q + r - 5
    assert {n: (n // ceil6(n), sigma(n)) for n in (7, 8, 9, 13, 14, 19)} == {
        7: (3, 1), 8: (4, 0), 9: (4, 1), 13: (4, 1), 14: (4, 2), 19: (4, 3)}
    assert [n for n in nonmult if n // ceil6(n) < 5] == [7, 8, 9, 13, 14, 19]
    for n in range(7, 201):                                                         # and the geometry agrees
        assert pp.min_gap(n) == ceil6(n) and pp.max_size(n) == n // ceil6(n)


def test_theorem_5_3_and_corollary_5_4_rigid_values_of_n():
    expected = {7, 8, 9, 10, 11, 13, 15, 16, 20, 21, 25, 26, 31}
    for n in range(7, 401):
        k, m = pp.max_size(n), pp.min_gap(n)
        unique = pp.count_classes(n, k)[0] == 1
        assert unique == (n - k * m <= 1), n
        assert unique == (n % 6 == 0 or n in expected), n


def test_proposition_3_3_neighbours_share_a_full_edge_when_6_divides_n():
    for n in (12, 18, 24, 36, 60):
        m = n // 6
        a = list(ps.neighbour(n, 0).exterior.coords)[:-1]
        b = list(ps.neighbour(n, m).exterior.coords)[:-1]
        shared = [(p, q) for p in a for q in b if math.dist(p, q) < 1e-9]
        side = 2 * math.sin(math.pi / n)
        assert len(shared) == 2, n                                                  # exactly two common vertices ...
        assert math.dist(shared[0][0], shared[1][0]) == pytest.approx(side, rel=1e-9)   # ... one side apart


def test_proposition_7_2_discretised_kissing_number():
    for n in range(20, 401):
        assert pp.max_size(n) == 5 + (n % 6 == 0)
    for m in (10, 50, 100):
        assert pp.max_size(6 * m) * pp.min_gap(6 * m) / (6 * m) == 1.0
    ceil6 = lambda n: -(-n // 6)
    for n in (601, 6001, 60001):                                                    # phi -> 5/6 along n = 6q + 1
        assert (5 * ceil6(n) / n) == pytest.approx(5 / 6 * (1 + 5 / n))