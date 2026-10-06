"""Build notebooks/03-prepare.ipynb for the pokemon project.

Two jobs, both from the interim `pokemon_clean` table:

  Job 1 — build the chart-ready / radar-input tables (materialized in DuckDB AND
          saved to data/processed/ as Parquet). `04-viz` ONLY consumes these; it
          must never shape chart tables off interim data. The four tables map to
          the four exploration hooks:
            chart_iconic_fingerprints  — curated icons (faceted small-multiples)
            chart_type_avg             — avg of 6 stats by primary type
            chart_generation_avg       — avg of 6 stats + BST by generation
            chart_legendary_vs_field   — avg of 6 stats, legendary/mythical vs rest
  Job 2 — export the sellable per-species dataset (CSV + Excel + Parquet) with a
          plain-English codebook for every column.

Radar normalization decision (documented in the notebook): every chart table
carries each raw stat AND a normalized 0..100 version using a SINGLE shared
denominator — the global max of any individual base stat across all 1025 species
(STAT_MAX = 255, HP Blissey). ONE shared max keeps the six radar spokes directly
comparable; per-stat min-max would distort the fingerprint and is NOT used.

The three AVERAGED tables ALSO carry a second normalized column set, suffix
`_navg`, on an AVERAGED scale (denominator AVG_STAT_MAX = the max averaged stat
across all three averaged tables), so their averaged radar polygons fill the
frame rather than cramping at ~40/100 on the 255 scale. The iconic (individual)
table keeps ONLY the 255-based *_norm — its extreme shapes are the point. Both
scales are honest, each shared across its peer group; see the notebook.

Regenerate with:  .venv/bin/python scripts/_build_nb_03_prepare.py
Then execute with:
    .venv/bin/python -m jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.kernel_name=pokemon-venv \
        --ExecutePreprocessor.timeout=600 notebooks/03-prepare.ipynb
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
# 03 — Prepare: chart-ready radar tables + sellable export

This stage has **two jobs**, both built from the interim `pokemon_clean` table
(1025 species) entirely in **DuckDB SQL**:

**Job 1 — build the chart-ready tables** (materialized in DuckDB *and* saved to
`data/processed/`). `04-viz` will **only consume** these four tables — it must
never shape chart data off the interim table — so the shaping is settled here,
one table per the four radar exploration hooks the owner wants:

| Table | One row per | Powers |
|---|---|---|
| `chart_iconic_fingerprints` | iconic Pokémon (12) | contrasting stat "fingerprints" (faceted small-multiples) |
| `chart_type_avg` | primary type (~18) | "is Steel really the defensive type?" |
| `chart_generation_avg` | generation (1..9) | "power creep over generations" |
| `chart_legendary_vs_field` | group (2) | "legendaries vs the field" |

**Job 2 — export the sellable package**: the per-species dataset (NOT the
aggregates) as CSV + Excel + Parquet with a plain-English codebook.
"""))

# ── Cell 1 — the normalization decision + fixed spoke order ─────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## The radar design — fixed spoke order + ONE shared normalization scale

**Fixed spoke order (used everywhere, consistently):**

> **HP · Attack · Defense · Sp. Atk · Sp. Def · Speed**

mapped to the columns `hp`, `attack`, `defense`, `special_attack`,
`special_defense`, `speed`. `04-viz` maps spokes mechanically from these column
names in exactly this order.

**Normalization — a SINGLE shared denominator across all six stats.** Radar
charts mislead when their axes aren't on a common scale. So every chart table
carries, alongside each raw stat, a normalized `*_norm` version on a shared
**0..100** scale computed as `100 * stat / STAT_MAX`, where `STAT_MAX` is the
**global maximum of any individual base stat across all 1025 species**:

> **`STAT_MAX = 255`**  — the single largest base stat value in the dex
> (Blissey's HP = 255; Shuckle's Defense & Sp. Def = 230; Kartana Attack = 181;
> Regieleki Speed = 200; Xurkitree Sp. Atk = 173).

We use this **one** denominator for all six axes — we do **NOT** per-stat
min-max normalize, because that would rescale each axis independently and
distort the fingerprint (a mediocre Speed could look maxed out). One shared max
keeps the six spokes directly comparable: a stat near 100 on the normalized
scale genuinely approaches the biggest stat any Pokémon has.

`STAT_MAX` is asserted below (recomputed from the data, must equal 255) so the
denominator can never silently drift.
"""))

# ── Cell 1b — the SECOND (averaged) scale ───────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## A SECOND scale for the AVERAGED charts — `AVG_STAT_MAX`

The 255-based `*_norm` scale above is the right scale for comparing
**individuals** (`chart_iconic_fingerprints`): Blissey's 255 HP is a real,
extreme shape and we *want* those polygons to be lopsided and spiky.

But the three **averaged** tables (`chart_type_avg`, `chart_generation_avg`,
`chart_legendary_vs_field`) are averages over dozens-to-hundreds of species, so
no averaged stat gets anywhere near 255 — the biggest averaged stat tops out
around ~130, i.e. only ~50/100 on the 255 scale. On a radar that means every
averaged polygon is cramped into the middle of the frame and the interesting
*shape* differences are hard to read.

So the averaged charts get a **second** normalized column set, suffix `_navg`,
on their own shared scale:

> **`<stat>_navg = clamp(100 * avg_stat / AVG_STAT_MAX, 0, 100)`**

where **`AVG_STAT_MAX`** is a **single shared denominator** = the largest
averaged stat value observed across **all six stat columns of all three
averaged tables**. Using one shared max (not per-table, not per-stat) means the
biggest averaged polygon reaches ~100 and **all three averaged charts stay
directly comparable to each other** on one scale.

Both scales are honest — each is shared across its peer group. The split is a
deliberate per-chart-type convention:

- `chart_iconic_fingerprints` (individuals) → use **`_norm`** (255 scale). No
  `_navg` is added there.
- the three averaged tables → use **`_navg`** (averaged scale) for the radar,
  while **keeping** their `_norm` columns too.

The subtitle on each averaged chart must later say it's normalized to the **max
average stat**, not the 255 individual max. `AVG_STAT_MAX` is computed from the
data below and documented so it can't silently drift.
"""))

# ── Cell 2 — setup ──────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
import sys, os
from pathlib import Path

# Navigate to project root regardless of how the kernel was launched
PROJECT = Path.cwd()
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
os.chdir(PROJECT)
sys.path.insert(0, str(PROJECT))

from src.ingest import load_config
from src.clean_quality import get_connection, run_sql, register_source, save_processed
from src.prepare import package_dataset

cfg = load_config("config.yaml")
con = get_connection(cfg)
print("Project:", cfg["project_name"])
print("pokemon_clean rows:", con.execute("SELECT COUNT(*) FROM pokemon_clean").fetchone()[0])
"""))

# ── Cell 3 — compute + assert STAT_MAX ──────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
### Compute the shared `STAT_MAX` denominator (and assert it)

The one number every normalized column divides by — the global max of any single
base stat across all species. Computed from the data so it can't drift; asserted
to equal 255.
"""))

cells.append(nbformat.v4.new_code_cell("""\
STAT_MAX = con.execute(\"\"\"
    SELECT GREATEST(MAX(hp), MAX(attack), MAX(defense),
                    MAX(special_attack), MAX(special_defense), MAX(speed))
    FROM pokemon_clean
\"\"\").fetchone()[0]
print("Shared STAT_MAX denominator:", STAT_MAX)
assert STAT_MAX == 255, f"Expected global stat max 255 (Blissey HP), got {STAT_MAX}"

# The six base stats in the FIXED canonical spoke order used everywhere.
STATS = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
print("Fixed spoke order:", STATS)
"""))

# ── Cell 3b — compute AVG_STAT_MAX across the three averaged groupings ───────
cells.append(nbformat.v4.new_markdown_cell("""\
### Compute the shared `AVG_STAT_MAX` denominator for the averaged charts

`AVG_STAT_MAX` = the single largest averaged stat value across **all six stat
columns of all three averaged groupings** (by primary type, by generation, and
legendary-vs-field). The three averaged tables divide their `_navg` columns by
this one number, so the biggest averaged polygon reaches ~100 and the three
averaged charts stay directly comparable. Computed from the data (not
hard-coded) so it can't drift.
"""))

cells.append(nbformat.v4.new_code_cell("""\
_avg_exprs = ", ".join(f"AVG({s}) AS {s}" for s in STATS)
_grp_cte = \"\"\"
WITH g AS (
    SELECT type_1 AS grp, {e} FROM pokemon_clean GROUP BY type_1
    UNION ALL
    SELECT CAST(generation AS VARCHAR) AS grp, {e} FROM pokemon_clean GROUP BY generation
    UNION ALL
    SELECT CASE WHEN is_legendary_or_mythical THEN 'leg' ELSE 'field' END AS grp, {e}
    FROM pokemon_clean GROUP BY is_legendary_or_mythical
)
\"\"\".format(e=_avg_exprs)

AVG_STAT_MAX = con.execute(_grp_cte + \"\"\"
    SELECT MAX(GREATEST(hp, attack, defense, special_attack, special_defense, speed))
    FROM g
\"\"\").fetchone()[0]
AVG_STAT_MAX = round(float(AVG_STAT_MAX), 4)
print("Shared AVG_STAT_MAX denominator (max averaged stat across the 3 averaged tables):", AVG_STAT_MAX)
assert 0 < AVG_STAT_MAX < STAT_MAX, AVG_STAT_MAX
"""))

# ── Cell 4 — helper SQL ──────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
### Normalization helpers

Small SQL-fragment builders so every chart table normalizes identically against
the shared `STAT_MAX`. `norm_select()` emits `ROUND(100.0*<expr>/STAT_MAX, 1) AS
<stat>_norm` for each of the six stats, given the raw expression (a column for
per-species tables, an `AVG(...)` for aggregates).
"""))

cells.append(nbformat.v4.new_code_cell("""\
def norm_select(expr=lambda s: s):
    \"\"\"Return a SQL fragment: one `<stat>_norm` column per stat on the 0..100
    shared scale. `expr(stat)` builds the raw expression for that stat
    (identity for per-row tables, e.g. `AVG(hp)` for aggregates).\"\"\"
    return ",\\n        ".join(
        f"ROUND(100.0 * ({expr(s)}) / {STAT_MAX}, 1) AS {s}_norm" for s in STATS
    )

def navg_select(expr=lambda s: s):
    \"\"\"Return a SQL fragment: one `<stat>_navg` column per stat on the AVERAGED
    0..100 scale (divides by the shared AVG_STAT_MAX, clamped to 0..100). Used
    ONLY by the three averaged tables so their polygons fill the frame.\"\"\"
    return ",\\n        ".join(
        f"ROUND(LEAST(100.0, GREATEST(0.0, 100.0 * ({expr(s)}) / {AVG_STAT_MAX})), 1) AS {s}_navg"
        for s in STATS
    )

def raw_select(expr=lambda s: s, round_to=None):
    \"\"\"Return a SQL fragment: the six raw stat columns (optionally ROUND-ed).\"\"\"
    def one(s):
        e = expr(s)
        return f"ROUND({e}, {round_to}) AS {s}" if round_to is not None else f"{e} AS {s}"
    return ",\\n        ".join(one(s) for s in STATS)

print(norm_select())
print()
print(navg_select(lambda s: f'AVG({s})'))
"""))

# ── Cell 5 — chart_iconic_fingerprints ───────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Job 1 · Table 1 — `chart_iconic_fingerprints`

A curated short list of **12 recognizable, stat-diverse icons** chosen to show
contrasting radar fingerprints:

- **Alakazam** — glass cannon (huge Sp. Atk + Speed, paper Defense)
- **Shuckle** — the extreme wall (max Defense + Sp. Def, almost no offense)
- **Steelix** — a second wall (physical Defense), Steel-type anchor
- **Snorlax** — HP/Sp.Def tank, slow
- **Garchomp** / **Dragonite** — sweepers (strong, fast, well-rounded pseudo-legends)
- **Charizard** / **Blastoise** — balanced starter final-evolutions (contrast: special vs bulk)
- **Machamp** — pure physical attacker
- **Gardevoir** — special attacker/support
- **Gyarados** — physical attacker with a famously low Sp. Atk
- **Pikachu** — the mascot (modest, Speed-leaning)

**Intent: faceted small-multiples** (one radar per Pokémon). Twelve polygons is
far more than the ≤3 that can be sensibly *overlaid*, so `04-viz` should facet
these — not overlay them. (A subset of ≤3 could be overlaid for a direct
head-to-head, e.g. Alakazam vs Shuckle vs Snorlax.)
"""))

cells.append(nbformat.v4.new_code_cell("""\
ICONS = [
    "pikachu", "charizard", "blastoise", "alakazam", "machamp", "gyarados",
    "snorlax", "dragonite", "steelix", "shuckle", "gardevoir", "garchomp",
]
icons_sql = ", ".join(f"'{s}'" for s in ICONS)

con.execute(f\"\"\"
    CREATE OR REPLACE TABLE chart_iconic_fingerprints AS
    SELECT
        species_id, name, slug, generation,
        type_1, type_2, is_legendary_or_mythical,
        {raw_select()},
        {norm_select()},
        base_stat_total
    FROM pokemon_clean
    WHERE slug IN ({icons_sql})
    ORDER BY array_position({[s for s in ICONS]}::VARCHAR[], slug)
\"\"\")
save_processed(run_sql("SELECT * FROM chart_iconic_fingerprints", con),
               cfg, "chart_iconic_fingerprints.parquet")
run_sql("SELECT name, hp, attack, defense, special_attack, special_defense, speed, "
        "base_stat_total FROM chart_iconic_fingerprints", con)
"""))

# ── Cell 6 — chart_type_avg ──────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Job 1 · Table 2 — `chart_type_avg`

Average of each of the six stats **by primary type** (`type_1`), one row per type
(~18 types), with raw averages, normalized averages, and a `n_species` count.
Powers the *"is Steel really the defensive type the numbers say?"* chart. Raw
averages rounded to 1 dp; `n_species` sums to 1025 (every species has exactly one
primary type).
"""))

cells.append(nbformat.v4.new_code_cell("""\
con.execute(f\"\"\"
    CREATE OR REPLACE TABLE chart_type_avg AS
    SELECT
        type_1,
        COUNT(*) AS n_species,
        {raw_select(lambda s: f'AVG({s})', round_to=1)},
        {norm_select(lambda s: f'AVG({s})')},
        {navg_select(lambda s: f'AVG({s})')}
    FROM pokemon_clean
    GROUP BY type_1
    ORDER BY defense DESC
\"\"\")
save_processed(run_sql("SELECT * FROM chart_type_avg", con),
               cfg, "chart_type_avg.parquet")
run_sql("SELECT type_1, n_species, defense, special_defense, attack, speed "
        "FROM chart_type_avg ORDER BY defense DESC", con)
"""))

# ── Cell 7 — chart_generation_avg ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Job 1 · Table 3 — `chart_generation_avg`

Average of each of the six stats **by generation** (1..9), one row per generation,
raw + normalized, plus `n_species` per gen and `avg_base_stat_total` (so a simple
"power creep" inflation line can be drawn straight from this table). `n_species`
matches the known per-gen counts (1=151, 2=100, 3=135, 4=107, 5=156, 6=72, 7=88,
8=96, 9=120).
"""))

cells.append(nbformat.v4.new_code_cell("""\
con.execute(f\"\"\"
    CREATE OR REPLACE TABLE chart_generation_avg AS
    SELECT
        generation,
        COUNT(*) AS n_species,
        {raw_select(lambda s: f'AVG({s})', round_to=1)},
        {norm_select(lambda s: f'AVG({s})')},
        {navg_select(lambda s: f'AVG({s})')},
        ROUND(AVG(base_stat_total), 1) AS avg_base_stat_total
    FROM pokemon_clean
    GROUP BY generation
    ORDER BY generation
\"\"\")
save_processed(run_sql("SELECT * FROM chart_generation_avg", con),
               cfg, "chart_generation_avg.parquet")
run_sql("SELECT generation, n_species, avg_base_stat_total, hp, attack, speed "
        "FROM chart_generation_avg ORDER BY generation", con)
"""))

# ── Cell 8 — chart_legendary_vs_field ────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Job 1 · Table 4 — `chart_legendary_vs_field`

Average of each of the six stats for **two groups** — legendary-or-mythical vs
the rest ("field") — one row per group (2 rows), raw + normalized, plus group
counts. Powers *"legendaries vs the field"*. `is_legendary_or_mythical` is true
for 94 species, so the two counts sum to 1025.
"""))

cells.append(nbformat.v4.new_code_cell("""\
con.execute(f\"\"\"
    CREATE OR REPLACE TABLE chart_legendary_vs_field AS
    SELECT
        CASE WHEN is_legendary_or_mythical
             THEN 'Legendary/Mythical' ELSE 'Field' END AS group_name,
        is_legendary_or_mythical,
        COUNT(*) AS n_species,
        {raw_select(lambda s: f'AVG({s})', round_to=1)},
        {norm_select(lambda s: f'AVG({s})')},
        {navg_select(lambda s: f'AVG({s})')},
        ROUND(AVG(base_stat_total), 1) AS avg_base_stat_total
    FROM pokemon_clean
    GROUP BY is_legendary_or_mythical
    ORDER BY is_legendary_or_mythical DESC
\"\"\")
save_processed(run_sql("SELECT * FROM chart_legendary_vs_field", con),
               cfg, "chart_legendary_vs_field.parquet")
run_sql("SELECT * FROM chart_legendary_vs_field", con)
"""))

# ── Cell 9 — chart-table QC ──────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
### QC the chart tables — fail loudly

- row counts (iconic=12, type_avg≈18, generation_avg=9, legendary_vs_field=2),
- every `*_norm` column is within 0..100 across all four tables,
- `chart_type_avg.n_species` sums to 1025,
- `chart_generation_avg.n_species` matches the known per-gen counts,
- `chart_legendary_vs_field.n_species` sums to 1025.
"""))

cells.append(nbformat.v4.new_code_cell("""\
STATS = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
NORM_COLS = [f"{s}_norm" for s in STATS]

counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in [
    "chart_iconic_fingerprints", "chart_type_avg",
    "chart_generation_avg", "chart_legendary_vs_field",
]}
print("row counts:", counts)
assert counts["chart_iconic_fingerprints"] == 12
assert counts["chart_type_avg"] == 18, counts["chart_type_avg"]
assert counts["chart_generation_avg"] == 9
assert counts["chart_legendary_vs_field"] == 2

# normalized columns within 0..100 across every chart table
for t in counts:
    bounds = ", ".join(f"MIN({c}) AS mn_{c}, MAX({c}) AS mx_{c}" for c in NORM_COLS)
    row = con.execute(f"SELECT {bounds} FROM {t}").df().iloc[0]
    lo = min(row[f"mn_{c}"] for c in NORM_COLS)
    hi = max(row[f"mx_{c}"] for c in NORM_COLS)
    assert 0 <= lo and hi <= 100, f"{t} norm out of 0..100: [{lo}, {hi}]"
    print(f"{t:<28} norm range [{lo:.1f}, {hi:.1f}]")

# coverage sums
# averaged tables: _navg columns within 0..100, and the biggest reaches ~100
NAVG_COLS = [f"{s}_navg" for s in STATS]
AVG_TABLES = ["chart_type_avg", "chart_generation_avg", "chart_legendary_vs_field"]
global_navg_max = 0.0
for t in AVG_TABLES:
    bounds = ", ".join(f"MIN({c}) AS mn_{c}, MAX({c}) AS mx_{c}" for c in NAVG_COLS)
    row = con.execute(f"SELECT {bounds} FROM {t}").df().iloc[0]
    lo = min(row[f"mn_{c}"] for c in NAVG_COLS)
    hi = max(row[f"mx_{c}"] for c in NAVG_COLS)
    assert 0 <= lo and hi <= 100, f"{t} navg out of 0..100: [{lo}, {hi}]"
    global_navg_max = max(global_navg_max, hi)
    print(f"{t:<28} navg range [{lo:.1f}, {hi:.1f}]")
assert abs(global_navg_max - 100.0) < 0.5, f"largest _navg should reach ~100, got {global_navg_max}"
print(f"largest _navg across the 3 averaged tables: {global_navg_max:.1f} (AVG_STAT_MAX={AVG_STAT_MAX})")
# iconic table must NOT carry _navg
iconic_cols = [r[0] for r in con.execute("DESCRIBE chart_iconic_fingerprints").fetchall()]
assert not any(c.endswith("_navg") for c in iconic_cols), "iconic table must not have _navg"

assert con.execute("SELECT SUM(n_species) FROM chart_type_avg").fetchone()[0] == 1025
assert con.execute("SELECT SUM(n_species) FROM chart_legendary_vs_field").fetchone()[0] == 1025
gen_counts = dict(con.execute(
    "SELECT generation, n_species FROM chart_generation_avg ORDER BY generation").fetchall())
expected = {1:151,2:100,3:135,4:107,5:156,6:72,7:88,8:96,9:120}
assert gen_counts == expected, gen_counts
print("\\nAll chart-table QC asserts passed.")
"""))

# ── Cell 10 — sanity figures ─────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
### Sanity figures the story will cite

Which primary type has the highest average Defense (is it Steel?), and which
generation has the highest average base-stat-total (the power-creep headline).
"""))

cells.append(nbformat.v4.new_code_cell("""\
print("Top-5 primary types by avg Defense:")
print(run_sql("SELECT type_1, defense, special_defense, n_species "
              "FROM chart_type_avg ORDER BY defense DESC LIMIT 5", con).to_string(index=False))
print("\\nGenerations by avg base_stat_total:")
print(run_sql("SELECT generation, avg_base_stat_total, n_species "
              "FROM chart_generation_avg ORDER BY avg_base_stat_total DESC", con).to_string(index=False))
print("\\nLegendary vs field (avg BST):")
print(run_sql("SELECT group_name, n_species, avg_base_stat_total "
              "FROM chart_legendary_vs_field", con).to_string(index=False))
"""))

# ── Cell 11 — export ─────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Job 2 — sellable export + codebook

Export the clean **per-species** analysis dataset (not the chart aggregates) from
`pokemon_clean` as CSV + Excel + Parquet (per `config.yaml` `export.formats`),
with a codebook describing **every column** in plain English. The redundant
lowercase `slug` helper is dropped from the export (the display `name` plus
`species_id` identify every row); the six base stats are the species' **current /
latest** base stats as served by PokéAPI.

`package_dataset()` calls `strip_pii()` internally — `strip_pii_columns` is empty
in config, so it's a no-op (as intended for this public pop-culture dataset).
Export name: **`pokemon_base_stats_v1`**.
"""))

cells.append(nbformat.v4.new_code_cell("""\
export_df = con.execute(\"\"\"
    SELECT
        species_id, name, generation,
        is_legendary, is_mythical, is_legendary_or_mythical,
        type_1, type_2,
        hp, attack, defense, special_attack, special_defense, speed,
        base_stat_total
    FROM pokemon_clean
    ORDER BY species_id
\"\"\").df()

codebook = {
    "species_id": "National Pokédex number (1..1025); unique per species. The species' dex id as served by PokéAPI.",
    "name": "Species display name, title-cased (e.g. 'Charizard', 'Ho-Oh').",
    "generation": "Game generation the species debuted in, as an integer 1..9 (Gen I = Red/Blue … Gen IX = Scarlet/Violet).",
    "is_legendary": "True if PokéAPI flags the species as Legendary.",
    "is_mythical": "True if PokéAPI flags the species as Mythical (event-distributed legendaries).",
    "is_legendary_or_mythical": "Convenience flag: True if is_legendary OR is_mythical (the 'not an ordinary Pokémon' group used in the legendaries-vs-field comparison).",
    "type_1": "Primary type, title-cased (e.g. 'Fire'). Every species has exactly one primary type.",
    "type_2": "Secondary type, title-cased, or empty/NULL for mono-type species (~499 of 1025).",
    "hp": "Base HP stat — current/latest value (health points).",
    "attack": "Base Attack stat — current/latest value (physical offense).",
    "defense": "Base Defense stat — current/latest value (physical bulk).",
    "special_attack": "Base Special Attack stat — current/latest value (special offense).",
    "special_defense": "Base Special Defense stat — current/latest value (special bulk).",
    "speed": "Base Speed stat — current/latest value (turn order).",
    "base_stat_total": "Sum of the six base stats (hp+attack+defense+special_attack+special_defense+speed); the headline 'BST' power proxy.",
}

notes = \"\"\"Source: PokéAPI (https://pokeapi.co/) — keyless public REST API. One row per
Pokémon species across all nine generations (1025 species).
License: PokéAPI data is freely available; Pokémon names/stats are
(c) Nintendo / Game Freak / The Pokemon Company (nominative/fair use, non-commercial).
Scope & method: base stats are the CURRENT / LATEST base stats PokeAPI serves for the
default form of each species (not per-game-era historical values; a handful of stats
have been rebalanced across generations and reflect the latest value). Type_2 is empty
for mono-type species. Generation is the debut generation. This is a fun-tier
pop-culture dataset; see SOURCES.md.\"\"\"

written = package_dataset(export_df, cfg, name="pokemon_base_stats_v1",
                          codebook=codebook, notes=notes)
written
"""))

# ── Cell 12 — provenance ─────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
### Register provenance for the processed chart tables

Record the four `chart_*` tables in the `_sources` metadata table so the project
keeps full provenance for everything downstream reads (all derived from
`pokemon_clean`, ultimately PokéAPI).
"""))

cells.append(nbformat.v4.new_code_cell("""\
AVG_TABLES = {"chart_type_avg", "chart_generation_avg", "chart_legendary_vs_field"}
for t in ["chart_iconic_fingerprints", "chart_type_avg",
          "chart_generation_avg", "chart_legendary_vs_field"]:
    navg_note = (
        f" Averaged table also carries *_navg columns on a second shared 0..100 scale "
        f"(denominator AVG_STAT_MAX={AVG_STAT_MAX}, the max averaged stat across all three "
        f"averaged tables) so averaged radar polygons fill the frame; the iconic (individual) "
        f"table uses *_norm only."
        if t in AVG_TABLES else
        " Individual (iconic) table uses the *_norm (255) scale only — no *_navg."
    )
    register_source(
        con, t,
        name="PokéAPI (derived)",
        url="https://pokeapi.co/",
        license="Freely available; names/stats (c) Nintendo/Game Freak/The Pokemon Company (nominative/fair use, non-commercial)",
        notes=f"Chart-ready table built in 03-prepare from pokemon_clean. "
              f"Raw stats + normalized *_norm columns on a shared 0..100 scale "
              f"(denominator STAT_MAX={STAT_MAX}, global max base stat across all species)."
              + navg_note,
        methodology="Aggregated in DuckDB SQL from the interim pokemon_clean table. "
                    "*_norm divides each stat by the single shared global individual max "
                    "(255) so all six radar spokes share one comparable scale. The averaged "
                    f"tables add *_navg = 100*avg_stat/AVG_STAT_MAX ({AVG_STAT_MAX}), a second "
                    "shared scale across the three averaged tables so their polygons fill the frame.",
        series_breaks="Base stats reflect current/latest values; a few stats were "
                      "rebalanced across game generations.",
    )
print(run_sql("SELECT duckdb_table, source_name FROM _sources ORDER BY duckdb_table", con).to_string(index=False))
"""))

# ── Cell 13 — next ───────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
---
**Next:** `04-viz.ipynb` — explore the four radar hooks by **consuming** these
`chart_*` tables (never re-shaping off interim data): iconic fingerprints
(faceted small-multiples), type averages, generation power-creep, and legendaries
vs the field. This is also the stage that builds the shared **radar/spider**
template. **Pause for owner review of the framing before `06-viz-social`.**
"""))

# ── Cell 14 — cleanup ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
---
## Cleanup
Close the DuckDB connection so the single-writer lock is released for other tools
(DBCode, other notebooks). Runs on "Run All".
"""))
cells.append(nbformat.v4.new_code_cell("con.close()\nprint('connection closed')"))

nb.cells = cells

out = Path("notebooks/03-prepare.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")
