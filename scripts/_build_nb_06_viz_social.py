"""Build notebooks/06-viz-social.ipynb for the pokemon project.

The owner reviewed `04-viz` and confirmed the social lineup + scales, so this
notebook renders the **publication-ready** set. It is a CONSUMER: it opens the DB
**read-only** and renders the four owner-approved radar charts from the chart-ready
tables that `03-prepare` built. It must NOT create any chart_* table.

Four charts, each rendered in TWO targets from the SAME config (so social and web
can't drift) — the standard two-target render system:
  - SOCIAL: full chrome (title/subtitle/source/watermark), twitter_landscape
            (1600x900) -> outputs/social/   (via render_chart, which also displays)
  - WEB:    web_mode=True (drops title/subtitle/source, keeps only the
            @unwelcomedata watermark), web preset (1664x936) -> outputs/web/
            (built from the same base config, saved + displayed inline)

Scale convention (locked in 03-prepare):
  - chart_iconic_fingerprints (12 individuals)  -> *_norm  (255 individual scale)
  - chart_type_avg / chart_generation_avg /
    chart_legendary_vs_field (averages)         -> *_navg  (averaged scale, so the
    biggest averaged polygon fills the frame)

Canonical spoke order, fixed EVERYWHERE: HP, Attack, Defense, Sp. Atk, Sp. Def, Speed.

Regenerate with:  .venv/bin/python scripts/_build_nb_06_viz_social.py
Then execute with:
    .venv/bin/python -m jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.kernel_name=pokemon-venv \
        --ExecutePreprocessor.timeout=900 notebooks/06-viz-social.ipynb
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
# 06 — Social (publication radar charts): Pokémon stat fingerprints

The owner reviewed `04-viz` and confirmed the framing + scale decisions, so this
notebook renders the **publication-ready** set. It **CONSUMES** the four
chart-ready tables `03-prepare` built and renders them read-only; it does **not**
build any chart table.

**Two-target render system (standard).** Each chart is rendered **twice from the
same config** so the two can't drift:

- **Social** — full chrome (title, subtitle, source, `@unwelcomedata` watermark),
  `twitter_landscape` (1600×900) → `outputs/social/`.
- **Web** — `web_mode=True` (drops title/subtitle/source, keeps only the
  `@unwelcomedata` watermark), `web` preset (1664×936) → `outputs/web/`. These get
  copied to `docs/` and embedded on the Pages site later, which supplies its own
  headings.

**Scale convention (locked in `03-prepare`).** Every spoke is 0–100, but the
*denominator* differs by chart type so polygons fill the frame appropriately:

- **`chart_iconic_fingerprints`** (12 *individuals*) → **`*_norm`** — the 255
  individual scale (STAT_MAX = Blissey's 255 HP). The dramatic glass-cannon /
  wall shapes depend on this scale.
- the three **averaged** tables (type / generation / legendary-vs-field) →
  **`*_navg`** — the *averaged* scale (denominator `AVG_STAT_MAX` = the single
  largest averaged stat, ≈111.1 = Steel's average Defense), so the biggest
  averaged polygon reaches the frame edge instead of topping out near 40/100.

**Fixed spoke order, used everywhere:** HP · Attack · Defense · Sp. Atk · Sp. Def · Speed.

*Titles are **descriptive** (house default — say what the chart is, don't state the
conclusion). Overlays keep to ≤3 polygons (both are 2). Read-only DuckDB, closed in
the Cleanup cell.*
"""))

# ── Cell 1 — info-preservation (web charts) ──────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Info-preservation (web charts)

Web mode **drops the title, subtitle, and source**, so any load-bearing fact that
lives ONLY in that chrome is lost on the web chart and must be restated in the
Pages README **above** each chart. The chart face itself keeps: the spoke labels
(HP/Attack/…/Speed), the facet captions (species / `Gen N` / group name), and the
overlay legend. What must TRAVEL to the page per chart:

1. **Iconic stat fingerprints (facet of 12)** — restate the scale: *base stats
   normalized 0–100 on the shared **255** (max single stat) scale*, and that the
   facets are ordered by base-stat total. (The 12 species names survive in-image as
   facet captions.)
2. **Legendaries vs the field (overlay of 2)** — the two polygons look like generic
   "two shapes" without the title. Restate: this is **average** base stats on the
   **averaged** scale; the polygons are **Legendary/Mythical (n=94, navy)** vs **the
   Field (n=931, teal)**; legendary sits outside the field on every axis (avg BST
   592 vs 411). The legend survives in-image, but the n counts and the
   averaged-scale note do NOT. **Also restate the base-forms-only caveat** ("base
   forms only; excludes megas & alternate forms") — it lives only in the subtitle,
   so web mode drops it.
3. **Generation power creep (facet of 9)** — restate: **average** base stats per
   generation on the **averaged** scale, Gen I → Gen IX; the polygon inflates with
   power creep (Gen 9 highest avg total). (The `Gen N` facet captions survive.)
   **Also restate the base-forms-only caveat** ("base forms only; excludes megas &
   alternate forms") — it lives only in the subtitle, so web mode drops it.
4. **Steel vs Electric vs Normal (overlay of 3)** — three bare polygons without
   the title. Restate: **average** base stats on the **averaged** scale; **Steel
   (navy)** = the highest average Defense of any type (its Defense corner reaches
   the frame edge) vs **Electric (gold)**, a frail/offensive type that reaches
   further on Speed and Sp. Atk, vs **Normal (spice red-orange)**, the baseline type
   in between. The legend survives in-image; the averaged-scale note and the "which
   is the defensive one" framing do NOT. **Also restate the base-forms-only caveat**
   ("base forms only; excludes megas & alternate forms") — it lives only in the
   subtitle, so web mode drops it.
"""))

# ── Cell 2 — setup (read-only) + render_pair helper ──────────────────────────
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
from IPython.display import Image as IPImage, display
from chart_factory import render_chart, _CHART_TYPES
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

# Output dirs.
SOCIAL_DIR = Path("outputs/social"); SOCIAL_DIR.mkdir(parents=True, exist_ok=True)
WEB_DIR = Path("outputs/web"); WEB_DIR.mkdir(parents=True, exist_ok=True)

# Spoke labels (fixed order). The *column* set differs per chart (_norm vs _navg).
SPOKES = ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]
NORM_COLS = ["hp_norm", "attack_norm", "defense_norm",
             "special_attack_norm", "special_defense_norm", "speed_norm"]
NAVG_COLS = ["hp_navg", "attack_navg", "defense_navg",
             "special_attack_navg", "special_defense_navg", "speed_navg"]
SCALE_255 = "Base stats, normalized 0\\u2013100 on a shared 255 scale (max single stat)"
SCALE_AVG = "Average of each base stat; normalized 0\\u2013100 to the highest type/group average"
SOURCE = "PokeAPI (pokeapi.co), retrieved 2026-10-05"
WATERMARK = "@unwelcomedata"


def render_pair(base_cfg: dict, filename: str):
    \"\"\"Render ONE chart config to BOTH targets so they can't drift.

    - social: full chrome at twitter_landscape -> outputs/social/<filename>.png,
      displayed inline (render_chart handles save + display).
    - web: web_mode=True at the web preset -> outputs/web/<filename>.png,
      built from the SAME base config, saved + displayed inline.
    \"\"\"
    # SOCIAL — full chrome. render_chart saves to outputs/social and displays.
    render_chart({
        **base_cfg,
        "preset": "twitter_landscape",
        "web_mode": False,
        "filename": filename,
    })

    # WEB — same config, chrome stripped, web canvas. Build via the radar builder
    # directly so we can save to outputs/web (render_chart only writes social).
    web_img = _CHART_TYPES["radar"]({
        **base_cfg,
        "preset": "web",
        "web_mode": True,
    }, con)
    web_path = WEB_DIR / f"{filename}.png"
    web_img.save(web_path, format="PNG", optimize=True)
    print(f"Saved web -> {web_path}  ({web_img.size[0]}x{web_img.size[1]} px)")
    display(IPImage(filename=str(web_path)))


print("Connected (read-only). Prepared chart tables present:", _required)
"""))

# ── Cell 3 — Chart 1: iconic fingerprints (facet, _norm) ─────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 1 — Iconic stat fingerprints (facet of 12)

Twelve iconic species, each as its own mini radar, so the archetypes read as
*shapes*: **glass cannons** spike Attack/Sp. Atk + Speed and collapse on the
defenses; **walls** do the opposite; **all-rounders** are fat near-regular
hexagons. This is the one chart that uses **`*_norm`** (the 255 individual scale) —
these are real single-species stats, and the 255 scale is what makes the dramatic
spiky/dented shapes legible (Blissey's 255 HP, Shuckle's wall, Alakazam's glass
cannon). Facet mode because 12 items is well past the ≤3-overlay guideline.
"""))

cells.append(nbformat.v4.new_code_cell("""\
icons = con.execute(\"\"\"
    SELECT * FROM chart_iconic_fingerprints
    ORDER BY base_stat_total, name
\"\"\").df()

render_pair({
    "type": "radar",
    "table": icons,
    "axis_cols": NORM_COLS,                 # individuals -> 255 scale
    "axis_labels": SPOKES,
    "label_col": "name",
    "facet": True,
    "ncols": 4,
    "max_value": 100,
    "title": "Pok\\u00e9mon stat fingerprints \\u2014 twelve iconic species",
    "subtitle": SCALE_255 + " \\u00b7 ordered by base-stat total \\u00b7 glass cannons spike Attack/Speed, walls spike the defenses",
    "source": SOURCE,
}, "01_iconic_fingerprints_facet")
"""))

# ── Cell 4 — Chart 2: legendaries vs field (overlay, _navg) ──────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 2 — Legendaries vs the field (overlay of 2)

A two-polygon **overlay**: the average fingerprint of legendary/mythical species
(**n=94**, navy) vs the average of everyone else — "the field" (**n=931**, teal).
The legendary polygon sits **outside the field on every axis** — legendaries aren't
specialized, they're uniformly stronger (avg base-stat total 592 vs 411). Uses
**`*_navg`** (the averaged scale) so the legendary polygon is large and fills the
frame rather than topping out near 40/100 on the 255 scale.
"""))

cells.append(nbformat.v4.new_code_cell("""\
leg = con.execute(\"\"\"
    SELECT * FROM chart_legendary_vs_field
\"\"\").df()
# The template now draws the smaller-area polygon LAST (on top), so the field
# (smaller) sits above the legendary polygon and isn't buried. Two clearly
# distinct categorical colors (cool navy vs bold warm gold) + visible outlines.

render_pair({
    "type": "radar",
    "table": leg,
    "axis_cols": NAVG_COLS,                 # averages -> averaged scale
    "axis_labels": SPOKES,
    "label_col": "group_name",
    "facet": False,                         # overlay the 2 polygons
    "max_value": 100,
    "series_colors": {
        "Field":              c("gold"),    # bold warm, drawn on top (smaller)
        "Legendary/Mythical": c("navy"),    # cool, the larger polygon
    },
    "title": "Legendary & mythical Pok\\u00e9mon vs the rest \\u2014 average base stats",
    "subtitle": SCALE_AVG + " \\u00b7 legendary/mythical (n=94, navy) sits outside the field (n=931, gold) on every axis \\u00b7 avg total 592 vs 411 \\u00b7 Base forms only; excludes megas & alternate forms.",
    "source": SOURCE,
}, "02_legendary_vs_field_overlay")
"""))

# ── Cell 5 — Chart 3: generation power creep (facet, _navg) ──────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 3 — Average base stats by generation (facet of 9)

The average fingerprint for each of the 9 generations, faceted Gen I → Gen IX.
Watch the polygon **inflate** across generations — the average Pokémon has grown
stronger on most axes over time (power creep); Gen 9 has the highest average
base-stat total (457.4) vs ~403–408 for the early generations. Uses **`*_navg`**
(the averaged scale) so the per-generation polygons are large and the inflation is
visible.
"""))

cells.append(nbformat.v4.new_code_cell("""\
gens = con.execute(\"\"\"
    SELECT * FROM chart_generation_avg
    ORDER BY generation
\"\"\").df()
gens = gens.copy()
gens["gen_label"] = "Gen " + gens["generation"].astype(str)

render_pair({
    "type": "radar",
    "table": gens,
    "axis_cols": NAVG_COLS,                 # averages -> averaged scale
    "axis_labels": SPOKES,
    "label_col": "gen_label",
    "facet": True,
    "ncols": 5,
    "max_value": 100,
    "title": "Average base stats by generation \\u2014 Gen I to Gen IX",
    "subtitle": SCALE_AVG + " \\u00b7 per generation \\u00b7 the polygon inflates with power creep (Gen 9 highest avg total) \\u00b7 Base forms only; excludes megas & alternate forms.",
    "source": SOURCE,
}, "03_generation_power_creep_facet")
"""))

# ── Cell 6 — Chart 4: Steel vs a frail type (overlay, _navg) ─────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Chart 4 — Steel vs Electric vs Normal (overlay of 3)

A ≤3-polygon **overlay** that makes the "is Steel really the defensive type?"
point: **Steel** (navy) has the highest average Defense of any type — its
Defense corner reaches the frame edge (Defense is the `AVG_STAT_MAX` denominator,
so Steel's Defense = 100 on this scale). Contrast with **Electric** (gold), a
frail, offense/speed-leaning type that reaches further on Speed and Sp. Atk but
caves in on Defense, and **Normal** (spice red-orange), the baseline "average" type
that sits in between. The shared **averaged** scale (`*_navg`) makes the trade-off
literal. The template draws the smaller-area polygon on top so none is buried.
"""))

cells.append(nbformat.v4.new_code_cell("""\
steel_vs = con.execute(\"\"\"
    SELECT * FROM chart_type_avg
    WHERE type_1 IN ('Steel', 'Electric', 'Normal')
\"\"\").df()
# Three polygons; the template draws the smaller-area one LAST (on top), so draw
# order here doesn't need pre-sorting. Three distinct categorical colors.

render_pair({
    "type": "radar",
    "table": steel_vs,
    "axis_cols": NAVG_COLS,                 # averages -> averaged scale
    "axis_labels": SPOKES,
    "label_col": "type_1",
    "facet": False,                         # overlay the 3 polygons
    "max_value": 100,
    "series_colors": {
        "Steel":    c("navy"),              # defensive type (cool)
        "Electric": c("gold"),              # frail / fast (warm)
        "Normal":   c("spice"),             # baseline, in between (spice red-orange
                                            # — matches the 04-viz exploration the
                                            # owner approved)
    },
    "title": "Steel vs Electric vs Normal \\u2014 average base-stat shape",
    "subtitle": SCALE_AVG + " \\u00b7 Steel has the highest average Defense of any type; Electric reaches further on Speed and Sp. Atk; Normal sits in between \\u00b7 Base forms only; excludes megas & alternate forms.",
    "source": SOURCE,
}, "04_steel_electric_normal_overlay")
"""))

# ── Cell 7 — parity check ────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Social / web parity check

Confirm the same four chart names landed in both `outputs/social/` and
`outputs/web/`, and print each file's pixel dimensions (social = 1600×900, web =
1664w; a facet may be taller than 936 but keeps the web width).
"""))

cells.append(nbformat.v4.new_code_cell("""\
from PIL import Image

NAMES = [
    "01_iconic_fingerprints_facet",
    "02_legendary_vs_field_overlay",
    "03_generation_power_creep_facet",
    "04_steel_electric_normal_overlay",
]
print("name                               social (WxH)      web (WxH)")
for n in NAMES:
    sp = SOCIAL_DIR / f"{n}.png"
    wp = WEB_DIR / f"{n}.png"
    ss = Image.open(sp).size if sp.exists() else None
    ws = Image.open(wp).size if wp.exists() else None
    print(f"{n:34s} {str(ss):17s} {str(ws)}")

social_set = {p.stem for p in SOCIAL_DIR.glob("*.png")} & set(NAMES)
web_set = {p.stem for p in WEB_DIR.glob("*.png")} & set(NAMES)
assert social_set == set(NAMES) == web_set, (
    f"parity mismatch: social={sorted(social_set)} web={sorted(web_set)}"
)
print("\\nParity OK: all 4 chart names present in BOTH outputs/social and outputs/web.")
"""))

# ── Cell 8 — cleanup ─────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("## Cleanup"))
cells.append(nbformat.v4.new_code_cell("""\
con.close()
print("Connection closed.")
"""))

nb.cells = cells

out = Path("notebooks/06-viz-social.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")
