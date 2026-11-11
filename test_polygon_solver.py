"""Tests for Polygon_solver.  Run:  pytest test_polygon_solver.py -q"""
import math

import pandas as pd
import pytest

try:                                   # saved as Polygon_solver.py (also accept the lowercase name)
    import Polygon_solver as ps
except ModuleNotFoundError:
    import polygon_solver as ps


@pytest.mark.parametrize("n, k, s", [
    (3, 3, 0), (4, 4, 0), (5, 5, 0), (6, 6, 0),     # k(n) = n, no skipping up to the hexagon
    (7, 3, 0), (8, 4, 0), (12, 6, 0),
    (13, 4, 1), (18, 6, 1), (19, 4, 2),
    (25, 5, 3),                                     # the 25_GON.ggb drawing: 5 neighbours, 3 skipped
    (54, 6, 7), (174, 6, 27), (400, 5, 65),
])
def test_known_values(n, k, s):
    sol = ps.solve(n)
    assert (sol.k, sol.s) == (k, s)


def test_closed_forms_match_exact_solver():
    assert ps.verify(n_max=150, workers=1) == []


def test_hexagonal_resonance_law():
    """k(n) = 6 exactly when 6 divides n (n >= 6), up to n = 120."""
    for n in range(6, 121):
        assert (ps.solve(n).k == 6) == (n % 6 == 0)


def test_s_is_non_decreasing():
    s = [ps.solve(n).s for n in range(3, 101)]
    assert s == sorted(s)


def test_min_spacing_is_ceil_n_over_6_from_7():
    for n in range(7, 101):
        assert ps.min_edge_spacing(n) == math.ceil(n / 6)


def test_arrangement_is_valid():
    for n in (7, 25, 34, 55, 100):
        sol = ps.solve(n)
        spacings = ps.arrangement(n)
        assert len(spacings) == sol.k
        assert sum(spacings) == n
        assert all(m >= sol.spacing for m in spacings)


def test_neighbour_shares_exactly_the_edge():
    """A reflected neighbour touches the central polygon along edge 0 only (no overlap)."""
    from shapely.geometry import Polygon
    n = 25
    central = Polygon(ps.regular_polygon(n))
    nb = ps.neighbour(n, 0)
    assert central.intersection(nb).area < 1e-12
    assert central.intersection(nb).length == pytest.approx(
        math.dist(ps.regular_polygon(n)[0], ps.regular_polygon(n)[1]))


def test_overlap_margin_is_far_above_tolerance():
    """The decisive overlap at spacing-1 must be much larger than the tolerance (numerical safety)."""
    worst = min(ps.solve(n).overlap_below for n in range(7, 151))
    assert worst > 1000 * ps.OVERLAP_TOL


def test_build_table_schema_and_preserves_labels():
    existing = pd.DataFrame([{
        "n": 30, "k_n": 6, "vertex_skipping": "Yes", "s_n": 3, "angle_str": "14\u03c0/15",
        "tension_state": "Maximally Tense (Hexagonal Resonance)", "angle_rad": 0.0, "angle_deg": 0.0,
        "is_hex_resonance": True, "is_max_tense": True, "is_phase_shift": False,
        "is_multiple_placements": False, "is_minimally_tense": False, "uses_skipping": True,
    }])
    t = ps.build_table(28, 32, existing, workers=1)
    assert list(t.columns) == ps.CORE_COLUMNS
    row30 = t[t.n == 30].iloc[0]
    assert row30.tension_state == "Maximally Tense (Hexagonal Resonance)" and row30.angle_str == "14\u03c0/15"
    assert (t[t.n == 29].iloc[0].tension_state) == "Not assessed"
    assert list(t.k_n) == [5, 5, 6, 5, 5]
    assert list(t.s_n) == [3, 3, 3, 4, 4]


def test_build_table_tolerates_missing_columns_and_blanks_unassessed_flags():
    existing = pd.DataFrame([
        {"n": 29, "k_n": 5, "tension_state": "Not assessed", "is_max_tense": False},   # no angle_str column
        {"n": 30, "k_n": 6, "tension_state": "Maximally Tense", "is_max_tense": True},
    ])
    t = ps.build_table(29, 31, existing, workers=1)
    assert t[t.n == 29].iloc[0].angle_str == "27\u03c0/29"
    assert pd.isna(t[t.n == 29].iloc[0].is_max_tense)          # unassessed -> blank, not False
    assert t[t.n == 30].iloc[0].is_max_tense == True            # assessed label kept