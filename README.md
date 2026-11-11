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
| `test_polygon_solver.py`                                                            | pytest suite for the solver (23 tests)                                                                                                                                                                                                                    |
| `Poly_Research.py`                                                                  | Streamlit dashboard: EDA, data cleaning, insights, nine plots (every chart lives here), **Geometric Solver** tab                                                                                                                                    |
| `requirements.txt`                                                                  | Python dependencies                                                                                                                                                                                                                                       |
| `polygon_conjoinability_Sheet1.csv`                                                 | corrected table, n = 3 to 400, 14 columns                                                                                                                                                                                                                 |
| `spreadsheet_kn_corrected.xlsx`                                                     | corrected workbook, data only, three sheets: `Sheet1` (main table), `Sheet5` (interior and exterior angles at multiples of 6), `Sheet7` (check of s(n) against the formula). It contains **no charts**: all charts are drawn by the dashboard |
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

The app loads `spreadsheet_kn_corrected.xlsx` from the same folder (then
`Copy of spreadsheet_kn.xlsx`, then `polygon_conjoinability_Sheet1.csv`), or any `.xlsx`
or CSV you upload in the sidebar. Keep `Polygon_solver.py` in the same folder. The
sidebar warns if any row disagrees with the exact formulas.

The **Visualisations** tab draws nine plots (k(n) and s(n) against n, dual-axis, heatmap,
s(n) against k(n), isomer emergence, formula analysis, an interactive 3D view, and internal angle
against s(n) in degrees and radians). The **Geometric Solver** tab solves and draws any single n, checks the loaded dataset
against the exact solver, and builds or extends the table (keeping existing tension labels).

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

### Tests

```bash
pytest test_polygon_solver.py -q
```

## Open questions

* Prove that the minimum non-overlapping spacing is `ceil(n/6)` for all n >= 7.
* Assess tension states and multiple placements for n > 55.
* Count all valid placements (the solver returns one arrangement, not the number of them).

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
