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