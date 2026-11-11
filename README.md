# Polygon Conjoinability Research

Research code and data on **polygon conjoinability**: how many copies of a regular
n-gon can be attached around a central n-gon, and how many of its vertices are left
untouched between them.

Author: Muhammad Zaid Bilal ([@M-zaid-bilal](https://github.com/M-zaid-bilal)) &nbsp;|&nbsp; Last updated: November 2026

## The problem

Take a regular n-gon (the *central* polygon). A *neighbour* is a copy of the same
regular n-gon attached to one full edge of the central polygon (its reflection across
that edge).

| Symbol         | Name            | Meaning                                                                                           |
| -------------- | --------------- | ------------------------------------------------------------------------------------------------- |
| **k(n)** | conjoinability  | how many neighbours fit around the central polygon without overlapping                            |
| **s(n)** | vertex skipping | untouched vertices of the central polygon between two adjacent neighbours at the tightest packing |

For n = 25 the answer is k = 5 and s = 3: five neighbours, with three untouched
central vertices between each pair. Neighbours at the tightest packing do not touch
each other; k counts how many fit, not a closed ring.

## Results

For every n from 3 to 400 the exact geometric solver (`Polygon_solver.py`) agrees with

```
k(n) = n                       for n <= 6
k(n) = floor( n / ceil(n/6) )  for n >= 7        (equals n for n <= 6 as well)
s(n) = max( 0, ceil(n/6) - 2 )
```

The reason is geometric: the smallest edge spacing at which two neighbours do not
overlap is `ceil(n/6)` edges (checked by exact polygon intersection for every n up to 400).

* **Hexagonal Resonance Law.** k(n) = 6 exactly when 6 divides n. This follows from the
  formula above, because `ceil(n/6) > n/6` unless 6 divides n.
* **Other values of k.** k(7) = 3; k = 4 at n = 8, 9, 13, 14, 19; k = 5 at every other
  non-multiple of 6, in particular for all of them from n = 20 up.
* **Vertex skipping** is monotone non-decreasing, first needed at n = 13 (s = 1), with
  s(6m) = m - 2 for every m >= 3 (for example s(174) = 27, s(400) = 65).

> **Status:** the `ceil(n/6)` spacing is a *numerical* result up to n = 400, not a proof.
> The model tests pairwise overlap of neighbours only and does not model tension states,
> phase shifts or multiple placements.

### Valid placements

A **placement** is a set of edges of the central n-gon that each carry a neighbour. **Overlap on
top of another polygon is invalid; touching is allowed.** Two kinds of valid placement occur, both
seen in the GeoGebra drawings:

* **open**: neighbours stay apart from each other (the 25-gon: 5 neighbours, 3 untouched vertices
  between each pair);
* **perfect ring**: every neighbour shares an edge with the next, so the ring closes exactly (the
  36-gon: 6 neighbours on edges 0, 6, 12, 18, 24, 30). This occurs exactly when 6 divides n, and
  it is then the only largest placement up to rotation.

Two neighbours overlap exactly when their edges are fewer than `m = ceil(n/6)` apart (verified by
exact polygon intersection for every n up to 400), so a placement is any set of edges whose cyclic
gaps are all at least `m`. `Polygon_placements.py` counts and lists them: for n = 34 there are
476 largest placements (5 neighbours) with every edge labelled, 14 up to rotation, and 10 up to
rotation and reflection. More than one distinct largest placement first appears at n = 14.

## Data corrections

An earlier version of the data contained entries that disagreed with the geometry
(the GeoGebra drawing of the 25-gon exposed the first one). They are fixed in place in
the `k_n` and `s_n` columns:

| n      | field | old | corrected |
| ------ | ----- | --- | --------- |
| 7      | k     | 4   | 3         |
| 7-11   | s     | 1   | 0         |
| 14-17  | s     | 2   | 1         |
| 25, 26 | s     | 2   | 3         |
| 174    | s     | 29  | 27        |

Two earlier hypotheses rested on these errors and are retired: the "step-back"
s(18) < s(17), and the "regime change" of s(6m) at m = 29. The corrected data has
neither. The dashboard keeps both in its hypothesis and error logs (E2, E5, E7, E8).

Rows n = 56 to 400 (except 174) were filled from the solver. Their **tension state is
`Not assessed`**: tension and multiple-placement labels exist only for n = 3 to 55 and
n = 174, and are left out of the dashboard's tension and isomer statistics.

## Repository contents

| File                                                                                  | What it is                                                                                                                                                                                                                                                |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Polygon_solver.py`                                                                 | exact geometric solver for k(n) and s(n); also a command-line tool                                                                                                                                                                                        |
| `Polygon_placements.py`                                                             | counts, lists and classifies **all valid placements** around a central n-gon (open or perfect ring); also a command-line tool                                                                                                                       |
| `test_polygon_solver.py`                                                            | pytest suite for the solver (23 tests)                                                                                                                                                                                                                    |
| `test_polygon_placements.py`                                                        | pytest suite for the placements module (50 tests, including brute-force geometric cross-checks)                                                                                                                                                           |
| `Poly_Research.py`                                                                  | Streamlit dashboard: EDA, data cleaning, insights, nine plots (every chart lives here), **Geometric Solver** and **Placements** tabs                                                                                                          |
| `requirements.txt`                                                                  | Python dependencies                                                                                                                                                                                                                                       |
| `polygon_conjoinability_Sheet1.csv`                                                 | corrected table, n = 3 to 400, 14 columns                                                                                                                                                                                                                 |
| `spreadsheet_kn_corrected_final.xlsx`                                               | corrected workbook, data only, three sheets: `Sheet1` (main table), `Sheet5` (interior and exterior angles at multiples of 6), `Sheet7` (check of s(n) against the formula). It contains **no charts**: all charts are drawn by the dashboard |
| `Copy of spreadsheet_kn.xlsx`                                                       | the **original, uncorrected** workbook, kept for provenance (the dashboard flags its 12 bad rows)                                                                                                                                                   |
| `polygon_conjoinability_report.pdf`, `Copy of Conjoinability_Presentation-2.pptx` | report and slides                                                                                                                                                                                                                                         |
| `Links.docx`                                                                        | list of links                                                                                                                                                                                                                                             |
| `Copy of *.pdf`                                                                     | reference papers (see file names)                                                                                                                                                                                                                         |
| `*.pyproj`, `*.sln`                                                               | Visual Studio Python project files                                                                                                                                                                                                                        |

### CSV columns

`n, k_n, vertex_skipping, s_n, angle_str, tension_state, angle_rad, angle_deg, is_hex_resonance, is_max_tense, is_phase_shift, is_multiple_placements, is_minimally_tense, uses_skipping`

## Getting started

Requires Python 3.10+ (tested on 3.12).

```bash
git clone https://github.com/M-zaid-bilal/Polygon_Conjoinability_Research_MZB.git
cd Polygon_Conjoinability_Research_MZB
pip install -r requirements.txt
```

### Dashboard

```bash
streamlit run Poly_Research.py
```

The app loads `spreadsheet_kn_corrected_final.xlsx` from the same folder (then
`Copy of spreadsheet_kn.xlsx`, then `polygon_conjoinability_Sheet1.csv`), or any `.xlsx`
or CSV you upload in the sidebar. Keep `Polygon_solver.py` and `Polygon_placements.py` in the same
folder. The sidebar warns if any row disagrees with the exact formulas.

The **Visualisations** tab draws nine plots (k(n) and s(n) against n, dual-axis, heatmap,
s(n) against k(n), isomer emergence, formula analysis, an interactive 3D view, and internal angle
against s(n) in degrees and radians). The **Geometric Solver** tab solves and draws any single n, checks the loaded dataset
against the exact solver, and builds or extends the table (keeping existing tension labels).

The **Placements** tab is interactive: enter n and the number of neighbours, choose whether rotations
and reflections count as the same pattern, and browse every valid arrangement as a thumbnail grid,
one large drawing (untouched vertices in red), and a table you can download. Each placement is
labelled open or perfect ring, and a button re-checks the shown placements by exact geometry.

### Solver

```bash
python Polygon_solver.py solve 25                 # k, s, edge spacing and one arrangement
python Polygon_solver.py verify --n-max 400       # exact solver vs closed forms, n = 3..400
python Polygon_solver.py table --n-max 400 \
       --existing polygon_conjoinability_Sheet1.csv --out table.csv
```

```python
import Polygon_solver as ps
sol = ps.solve(174)          # Solution(n=174, spacing=29, k=6, s=27, ...)
ps.k_closed(174), ps.s_closed(174)
ps.build_table(3, 400)       # pandas DataFrame in the CSV schema
```

Solving every n from 3 to 400 takes about 3 seconds on one core.

### Placements

```bash
python Polygon_placements.py count 34                       # how many placements of each size
python Polygon_placements.py list 34 --size 5 --symmetry dihedral --limit 10
python Polygon_placements.py check --n-max 400              # re-verify the overlap rule by exact geometry
```

```python
import Polygon_placements as pp
pp.count_labelled(34, 5)                       # 476 placements of 5 neighbours (edges labelled)
pp.count_classes(34, 5)                        # (14, 10): up to rotation, up to rotation + reflection
for p in pp.iter_placements(36, 6):            # lazy; use limit=... for huge spaces
    print(p.edges, p.gaps, p.kind)             # (0, 6, 12, 18, 24, 30) (6, 6, 6, 6, 6, 6) perfect ring
pp.list_placements(34, 5, "dihedral", limit=10, order="balanced")
```

Counts are exact closed forms (no enumeration), so they work for any n, for example about 69 million
labelled largest placements at n = 400; enumeration is lazy.

### Tests

```bash
pytest -q                          # both test files, 73 tests
```

## Open questions

* Prove that the minimum non-overlapping spacing is `ceil(n/6)` for all n >= 7.
* Assess tension states and multiple placements for n > 55.
* Relate the placement counts to the "Multiple Placements (2)" labels in the data (n = 34 to 55): under the
  no-overlap rule n = 34 has 10 distinct largest placements, so that label must mean something stricter.

## License

No license has been chosen yet.

## Citation

```bibtex
@misc{polygon_conjoinability_2026,
  author = {Muhammad Zaid Bilal},
  title  = {Polygon Conjoinability Research},
  year   = {2026},
  url    = {https://github.com/M-zaid-bilal/Polygon_Conjoinability_Research_MZB}
}
```
