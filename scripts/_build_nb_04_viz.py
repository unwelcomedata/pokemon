"""Build notebooks/04-viz.ipynb for the pokemon project.

04-viz is a CONSUMER: it opens the DB **read-only** and renders the four radar
exploration hooks from the chart-ready tables that `03-prepare` built. It must
NOT create any chart_* table or shape aggregates off `pokemon_clean` — that is
03's job. If a cut turns out to be missing, the fix is to amend 03 and re-run it,
not to build it here.

This is the project that introduces the kit's first POLAR template
(`radar`/`spider`, in `shared/chart_templates.py`). All four charts use the shared
NORMALIZED columns (`*_norm`, 0..100 on a single 255 scale) so every spoke means
the same thing in every chart and the polygon shape is a comparable "fingerprint".

Radar layout modes used here:
  - FACET (small-multiples grid) for the many-item charts — iconic species (12),
    types (18), generations (9).
  - OVERLAY (<=3 polygons on one radar) for the direct comparisons — Steel vs a
    frail type, and legendaries vs the field.

Canonical spoke order, fixed EVERYWHERE: HP, Attack, Defense, Sp. Atk, Sp. Def, Speed.

Regenerate with:  .venv/bin/python scripts/_build_nb_04_viz.py
Then execute with:
    .venv/bin/python -m jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.kernel_name=pokemon-venv \
        --ExecutePreprocessor.timeout=900 notebooks/04-viz.ipynb
"""
from pathlib import Path

import nbformat

nb = nbformat.v4.new_notebook()
nb.metadata = {
    "kernelspec": {
        "display_name": "Python 3",
        "language": "python",
        "name": "python3",
    },
    "language_info": {"name": "python", "version": "3.14"},
}

cells = []

# ── Cell 0 — title ──────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
# 04 — Visualization: Pokémon stat fingerprints (radar exploration)

This notebook explores the Pokémon base-stat data as **radar / spider charts** —
the kit's first POLAR template — to see which angles are worth building as social
charts later. It **CONSUMES** the four chart-ready tables built in `03-prepare`
and renders them read-only; it does **not** build any chart table (that is 03's
job). Run `03-prepare.ipynb` first.

Every chart plots the **shared normalized columns** (`*_norm`): each of the six
base stats scaled 0–100 against ONE global denominator (STAT_MAX = 255, the
highest single base stat in the game — Blissey's HP). Because every spoke uses the
same scale, the *shape* of a polygon is a comparable **fingerprint**: a spike on
one axis and a dent on another mean the same thing in every chart.

**Fixed spoke order, used everywhere:** HP · Attack · Defense · Sp. Atk · Sp. Def · Speed.

**Four hooks explored (all four, per the owner):**
1. **Iconic stat fingerprints** — a faceted grid of 12 iconic species (glass
   cannons vs walls at a glance).
2. **Average stat polygon by type** — faceted grid of all 18 primary types, plus
   an overlay that tests "is Steel really the defensive type?".
3. **Generation power creep** — faceted grid of the 9 generations' average polygon
   (watch it inflate), with the avg base-stat total per generation alongside.
4. **Legendaries vs the field** — an overlay of two polygons (legendary/mythical
   average vs everyone else).

These are **exploratory** (the matplotlib-equivalent iteration step). No
`06-viz-social` work happens here — framing is settled first, then social is built
once the owner confirms.
"""))

# ── Cell 1 — setup (read-only) ───────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
import sys, os
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

PROJECT = Path.cwd()
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT / "src"))

SHARED = PROJECT.parent.parent / "shared"
if str(SHARED) not in sys.path:
    sys.path.insert(0, str(SHARED))

import duckdb
import pandas as pd
from chart_factory import render_chart
from colors import c

DB_PATH = "data/project.duckdb"

# 03-prepare is the writer; this notebook only reads. Open read-only.
con = duckdb.connect(DB_PATH, read_only=True)

# Guard: the chart-ready tables must already exist (built by 03-prepare).
_tables = [t[0] for t in con.execute("SHOW TABLES").fetchall()]
_required = [
    "chart_iconic_fingerprints", "chart_type_avg",
    "chart_generation_avg", "chart_legendary_vs_field",
]
_missing = [t for t in _required if t not in _tables]
assert not _missing, (
    f"Prepared chart tables missing: {_missing}. "
    "Run notebooks/03-prepare.ipynb first (it builds the chart_* tables)."
)
print("Connected (read-only). Prepared chart tables present:", _required)

# The six normalized spoke columns, in the FIXED canonical order, and their
# pretty labels. Reused by every chart so the spoke order never drifts.
NORM_COLS = ["hp_norm", "attack_norm", "defense_norm",
             "special_attack_norm", "special_defense_norm", "speed_norm"]
SPOKES = ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]
SCALE_NOTE = "Base stats, normalized 0\\u2013100 on a shared 255 scale"
SOURCE = "PokeAPI (pokeapi.co), retrieved 2026-10-05"
"""))

# ── Cell 2 — hook 1: iconic fingerprints (FACET) ─────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Hook 1 — Iconic stat fingerprints (faceted small multiples)

Twelve iconic species, each as its own mini radar, so the archetypes jump out as
*shapes*:

- **Glass cannons** — spike on Attack/Sp. Atk and Speed, collapse on the defenses
  (e.g. Alakazam: huge Sp. Atk + Speed, paper defenses).
- **Walls** — the inverse: big Defense / Sp. Def, little Speed (Shuckle is the
  extreme — enormous defenses, almost nothing else; Steelix, Snorlax lean wall).
- **All-rounders** — fat, near-regular hexagons (Dragonite, Garchomp — strong on
  every axis, which is why pseudo-legendaries feel oppressive).

Twelve items is well past the ≤3-overlay guideline, so this uses the radar's
**facet mode** (a grid of small radars). The shared 0–100 scale means a big
polygon = genuinely high stats, not a rescaling artifact.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Order the 12 icons by base-stat total so similar-sized fingerprints sit near
# each other (reading left-to-right roughly weakest -> strongest overall).
icons = con.execute(\"\"\"
    SELECT * FROM chart_iconic_fingerprints
    ORDER BY base_stat_total, name
\"\"\").df()

render_chart({
    "type": "radar",
    "table": icons,                       # inline DataFrame (factory accepts a df under "table")
    "axis_cols": NORM_COLS,
    "axis_labels": SPOKES,
    "label_col": "name",
    "facet": True,
    "ncols": 4,
    "max_value": 100,
    "title": "Pok\\u00e9mon stat fingerprints \\u2014 twelve iconic species",
    "subtitle": SCALE_NOTE + " \\u00b7 ordered by base-stat total \\u00b7 glass cannons spike Attack/Speed, walls spike the defenses",
    "source": SOURCE,
    "preset": "twitter_landscape",
    "filename": "01_iconic_fingerprints_facet",
})
"""))

# ── Cell 3 — hook 2a: all types facet ────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Hook 2 — Average stat polygon by type

Each primary type's **average** fingerprint across all its species. First a facet
of all 18 types to scan them, then an overlay that tests the specific claim.

**Note on polygon size:** these are *averages over hundreds of species*, so the
polygons are much smaller than the iconic individuals above (a type's average
stat rarely exceeds ~110/255 ≈ 43 on the 0–100 scale). They're all drawn on the
same 0–100 scale as every other chart, so sizes stay comparable across the
notebook — the interesting signal here is the *shape* (which axis each type leans
on), not the overall area.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# All 18 types, ordered by average Defense so the defensive types cluster first
# and the shape differences are easy to scan.
types_all = con.execute(\"\"\"
    SELECT * FROM chart_type_avg
    ORDER BY defense DESC, type_1
\"\"\").df()

render_chart({
    "type": "radar",
    "table": types_all,
    "axis_cols": NORM_COLS,
    "axis_labels": SPOKES,
    "label_col": "type_1",
    "facet": True,
    "ncols": 6,
    "max_value": 100,
    "title": "Average stat fingerprint by primary type",
    "subtitle": SCALE_NOTE + " \\u00b7 mean of each type's species \\u00b7 ordered by average Defense",
    "source": SOURCE,
    "preset": "twitter_landscape",
    "filename": "02a_type_avg_facet",
})
"""))

# ── Cell 4 — hook 2b: Steel vs frail overlay ─────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
### Is Steel really the defensive type? (overlay)

A direct ≤3-polygon **overlay** makes the point the facet only hints at. **Steel**
has the highest average Defense of any type (111.1 raw). Contrast it with two
offense/speed-leaning types — **Electric** (fastest average, frail) and **Normal**
(frail, middling) — and Steel's Defense/Sp. Def corner visibly bulges out past
the other two, while they reach further on Speed. The shared scale makes the
trade-off literal: you can see the defensive mass Steel buys and the speed it
gives up.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Steel (the defensive wall) vs two frail, offense/speed types. <=3 polygons.
steel_vs = con.execute(\"\"\"
    SELECT * FROM chart_type_avg
    WHERE type_1 IN ('Steel', 'Electric', 'Normal')
\"\"\").df()
# Fix overlay order (Steel last so its outline/vertices sit on top).
_order = {"Electric": 0, "Normal": 1, "Steel": 2}
steel_vs = steel_vs.sort_values("type_1", key=lambda s: s.map(_order)).reset_index(drop=True)

render_chart({
    "type": "radar",
    "table": steel_vs,
    "axis_cols": NORM_COLS,
    "axis_labels": SPOKES,
    "label_col": "type_1",
    "facet": False,                    # overlay the 3 polygons on one radar
    "max_value": 100,
    "series_colors": {
        "Steel":    c("navy"),
        "Electric": c("gold"),
        "Normal":   c("spice"),
    },
    "title": "Average type fingerprint \\u2014 Steel vs Electric vs Normal",
    "subtitle": SCALE_NOTE + " \\u00b7 Steel has the highest average Defense of any type (111 raw); the frail types reach further on Speed",
    "source": SOURCE,
    "preset": "twitter_landscape",
    "filename": "02b_steel_vs_frail_overlay",
})
"""))

# ── Cell 5 — hook 3: generation power creep (FACET) ──────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Hook 3 — Generation power creep

The average fingerprint for each of the 9 generations, faceted in order. Watch the
polygon **inflate** across generations: the average Pokémon has grown stronger on
most axes over time (power creep). Generation 9 has the highest average base-stat
total (457.4) vs ~403–408 for the early generations.

The companion cell below prints the average base-stat total per generation — the
single-number summary of the same trend the radars show.
"""))

cells.append(nbformat.v4.new_code_cell("""\
gens = con.execute(\"\"\"
    SELECT * FROM chart_generation_avg
    ORDER BY generation
\"\"\").df()

# Label each facet "Gen N" rather than a bare number.
gens = gens.copy()
gens["gen_label"] = "Gen " + gens["generation"].astype(str)

render_chart({
    "type": "radar",
    "table": gens,
    "axis_cols": NORM_COLS,
    "axis_labels": SPOKES,
    "label_col": "gen_label",
    "facet": True,
    "ncols": 5,
    "max_value": 100,
    "title": "Average stat fingerprint by generation",
    "subtitle": SCALE_NOTE + " \\u00b7 mean of each generation's species \\u00b7 the polygon inflates with power creep (Gen 9 highest avg total)",
    "source": SOURCE,
    "preset": "twitter_landscape",
    "filename": "03_generation_power_creep_facet",
})
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Companion single-number view: average base-stat total per generation (the same
# power-creep trend the radars show, as one number).
bst = con.execute(\"\"\"
    SELECT generation, n_species, ROUND(avg_base_stat_total, 1) AS avg_bst
    FROM chart_generation_avg
    ORDER BY generation
\"\"\").df()
print("Average base-stat total by generation:")
print(bst.to_string(index=False))
print()
print(f"Lowest:  Gen {int(bst.loc[bst['avg_bst'].idxmin(),'generation'])}  ({bst['avg_bst'].min()})")
print(f"Highest: Gen {int(bst.loc[bst['avg_bst'].idxmax(),'generation'])}  ({bst['avg_bst'].max()})")
"""))

# ── Cell 6 — hook 4: legendaries vs field (OVERLAY) ──────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Hook 4 — Legendaries vs the field

A two-polygon **overlay**: the average fingerprint of legendary/mythical species
vs the average of everyone else ("the field"). The legendary polygon sits
**outside the field polygon on every axis** — legendaries aren't specialized, they
are uniformly stronger. The gap is large: average base-stat total 592 for
legendaries/mythicals vs 411 for the field.
"""))

cells.append(nbformat.v4.new_code_cell("""\
leg = con.execute(\"\"\"
    SELECT * FROM chart_legendary_vs_field
    ORDER BY is_legendary_or_mythical       -- field (0) first, legendary (1) on top
\"\"\").df()

render_chart({
    "type": "radar",
    "table": leg,
    "axis_cols": NORM_COLS,
    "axis_labels": SPOKES,
    "label_col": "group_name",
    "facet": False,                    # overlay the 2 polygons
    "max_value": 100,
    "series_colors": {
        "Field":              c("teal_mid"),
        "Legendary/Mythical": c("navy"),
    },
    "title": "Average stat fingerprint \\u2014 legendaries vs the field",
    "subtitle": SCALE_NOTE + " \\u00b7 legendary/mythical sits outside the field on every axis (avg total 592 vs 411)",
    "source": SOURCE,
    "preset": "twitter_landscape",
    "filename": "04_legendary_vs_field_overlay",
})
"""))

# ── Cell 7 — framing notes ───────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Story framing — candidate angles for social charts

From this exploration, the radar fingerprints read well at four grains:

1. **Iconic fingerprints (facet)** — the clearest "shape = archetype" teaching
   chart; glass cannon vs wall vs all-rounder is instantly legible. Strong lead
   candidate. Could also pull a 3-up overlay of one glass cannon (Alakazam) vs one
   wall (Shuckle) vs one all-rounder (Garchomp) for a punchier single radar.
2. **Steel vs frail (overlay)** — a clean, argument-driven single radar ("is Steel
   really the defensive type?"). Good standalone.
3. **Power creep (facet)** — the inflating polygon across generations; pairs with
   the one-number avg-BST trend.
4. **Legendaries vs the field (overlay)** — simple, strong two-polygon contrast.

**Open question for 03 (feedback loop, do NOT fix here):** the averaged tables
(type/gen/legendary) top out around 40/100 on the shared scale, so their polygons
are small next to the iconic individuals. If a social chart wants bigger averaged
polygons, the right move is to decide a scale convention in `03-prepare` (e.g. a
separate "averaged" normalized column scaled to the max *type-average* stat, kept
alongside the 255-scale columns) and re-run 03 — not to rescale inside this viz
notebook.

⏸ **No `06-viz-social` work until the owner reviews these and confirms the
lineup.**
"""))

# ── Cell 8 — cleanup ─────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/04-viz.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")
