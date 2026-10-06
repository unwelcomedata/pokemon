"""Build 02-clean.ipynb for the pokemon project.

Regenerate with:  .venv/bin/python scripts/_build_nb_02_clean.py
Then execute with: .venv/bin/python -m jupyter nbconvert --to notebook \
    --execute --inplace --ExecutePreprocessor.timeout=600 notebooks/02-clean.ipynb
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
# 02 — Clean: standardize `pokemon_raw` → `pokemon_clean`

PokéAPI data lands quite clean, so this stage is **light**. It does **cleaning
and standardization only** — no aggregation, no chart-ready/`chart_*` tables
(those belong in `03-prepare`). All work happens **inside DuckDB**.

What this notebook standardizes, and why:

- **`generation` → int 1..9.** The raw label is `generation-i` … `generation-ix`
  (roman numerals). We map it to a clean integer so it sorts and plots naturally.
  The mapping is asserted to cover all 9 labels (fails loudly if any is unmapped).
- **Title-case for display.** `name`, `type_1`, `type_2` arrive lowercase
  (`bulbasaur`, `grass`). We title-case them for human-facing display, keep
  `type_2` NULL where a species is mono-type, and keep the original lowercase
  `name` as a `slug` column (useful for joins / API round-trips).
- **Stat columns unchanged.** The six base stats (`hp`, `attack`, `defense`,
  `special_attack`, `special_defense`, `speed`) and `base_stat_total` are already
  correct ints and are passed through untouched. We **re-assert**
  `base_stat_total == hp+attack+defense+special_attack+special_defense+speed`
  for every row (fails loudly on any mismatch).
- **Convenience flag.** `is_legendary_or_mythical = is_legendary OR is_mythical`
  — a derived boolean for the later "legendaries vs the field" chart. This is a
  per-row flag, **not** an aggregated table.
- **Dedupe on `species_id`** (already unique; asserted to stay 1025 rows).

Output: interim Parquet `data/interim/pokemon_clean.parquet` via `save_interim()`.
"""))

# ── Cell 1 — setup ──────────────────────────────────────────────────────────
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
from src.clean_quality import (
    get_connection, run_sql, quality_report, save_interim, titlecase_sql,
)
import pandas as pd

cfg = load_config("config.yaml")
con = get_connection(cfg)
print(f"Project: {cfg['project_name']}")
print("Raw rows:", con.execute("SELECT COUNT(*) FROM pokemon_raw").fetchone()[0])
"""))

# ── Cell 2 — generation mapping ──────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## 1. Map `generation` roman-numeral labels → int 1..9

The raw column is `generation-i` … `generation-ix`. We first confirm the set of
labels is exactly the nine we expect — **failing loudly** if any unexpected or
unmapped label appears — then do the roman→int conversion in SQL below.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Guard: the distinct raw labels must be exactly our 9 known generations.
GEN_MAP = {
    "generation-i": 1, "generation-ii": 2, "generation-iii": 3,
    "generation-iv": 4, "generation-v": 5, "generation-vi": 6,
    "generation-vii": 7, "generation-viii": 8, "generation-ix": 9,
}
raw_gens = set(
    con.execute("SELECT DISTINCT generation FROM pokemon_raw").df()["generation"]
)
unmapped = raw_gens - set(GEN_MAP)
assert not unmapped, f"Unmapped generation label(s): {sorted(unmapped)}"
missing = set(GEN_MAP) - raw_gens
assert not missing, f"Expected generation label(s) absent from raw: {sorted(missing)}"
print(f"All {len(raw_gens)} generation labels map cleanly to int 1..9.")
"""))

# ── Cell 3 — the cleaning SQL ────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## 2. Build the cleaned table in DuckDB

A single SQL pass: roman→int generation, title-cased display strings, the
original lowercase slug, the stat columns passed through, and the convenience
`is_legendary_or_mythical` flag. Deduped on `species_id`.
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Clean entirely inside DuckDB (not pandas chains), per workspace norms.
# We materialize an interim DuckDB table `pokemon_clean` so the QC asserts and
# quality_report() below run against a real table (and dedup DISTINCT applies).
# - CASE maps the roman-numeral generation label to an int 1..9.
# - titlecase_sql() title-cases display strings (DuckDB has no INITCAP);
#   slug keeps the raw lowercase name for joins / API round-trips.
# - type_2 stays NULL for mono-type species.
# - stat columns + base_stat_total pass through unchanged.
name_tc = titlecase_sql("name")
type1_tc = titlecase_sql("type_1")
type2_tc = titlecase_sql("type_2")

con.execute(f\"\"\"
    CREATE OR REPLACE TABLE pokemon_clean AS
    SELECT
        species_id,
        {name_tc}                                  AS name,
        name                                       AS slug,
        CASE generation
            WHEN 'generation-i'    THEN 1
            WHEN 'generation-ii'   THEN 2
            WHEN 'generation-iii'  THEN 3
            WHEN 'generation-iv'   THEN 4
            WHEN 'generation-v'    THEN 5
            WHEN 'generation-vi'   THEN 6
            WHEN 'generation-vii'  THEN 7
            WHEN 'generation-viii' THEN 8
            WHEN 'generation-ix'   THEN 9
        END::INTEGER                               AS generation,
        is_legendary,
        is_mythical,
        (is_legendary OR is_mythical)              AS is_legendary_or_mythical,
        {type1_tc}                                 AS type_1,
        CASE WHEN type_2 IS NULL THEN NULL
             ELSE {type2_tc} END                   AS type_2,
        hp, attack, defense, special_attack, special_defense, speed,
        base_stat_total
    FROM (SELECT DISTINCT * FROM pokemon_raw)
    ORDER BY species_id
\"\"\")

pokemon_clean = run_sql("SELECT * FROM pokemon_clean ORDER BY species_id", con)
print("pokemon_clean.shape:", pokemon_clean.shape)
pokemon_clean.head()
"""))

# ── Cell 4 — QC asserts ──────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## 3. QC asserts — fail loudly

- row count stayed at 1025 (dedupe on `species_id` changed nothing),
- `species_id` is unique,
- `generation` covers exactly ints 1..9 with no NULLs,
- `base_stat_total` equals the sum of the six base stats for **every** row.
"""))

cells.append(nbformat.v4.new_code_cell("""\
n = len(pokemon_clean)
assert n == 1025, f"Expected 1025 rows, got {n}"
assert pokemon_clean["species_id"].is_unique, "species_id is not unique"

gens = set(pokemon_clean["generation"].tolist())
assert gens == set(range(1, 10)), f"generation values off: {sorted(gens)}"
assert pokemon_clean["generation"].notna().all(), "NULL generation present"

# Re-assert base_stat_total == sum of the six base stats (in SQL, over the clean table).
mismatches = run_sql(\"\"\"
    SELECT COUNT(*) AS n
    FROM pokemon_clean
    WHERE base_stat_total
          <> (hp + attack + defense + special_attack + special_defense + speed)
\"\"\", con)["n"].iloc[0]
assert mismatches == 0, f"base_stat_total mismatch rows: {mismatches}"

print("QC OK — 1025 rows, species_id unique, generation 1..9, 0 BST mismatches.")
"""))

# ── Cell 5 — quality report ──────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## 4. Quality report

`quality_report()` prints row count, duplicate rows, and null % per column.
`type_2` is legitimately ~49% null (mono-type species) — expected, not a defect.
"""))

cells.append(nbformat.v4.new_code_cell("""\
qc = quality_report(pokemon_clean, "pokemon_clean", con, max_null_pct=0.60)
"""))

# ── Cell 6 — final inspection ────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## 5. Final inspection — head, row count, per-generation counts
"""))

cells.append(nbformat.v4.new_code_cell("""\
print("Rows:", len(pokemon_clean))
print("\\nGeneration counts (1..9):")
print(pokemon_clean["generation"].value_counts().sort_index().to_string())
print("\\nLegendary-or-mythical:",
      int(pokemon_clean["is_legendary_or_mythical"].sum()),
      "of", len(pokemon_clean))
pokemon_clean.head(10)
"""))

# ── Cell 7 — save interim ────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## 6. Save interim Parquet

Write `data/interim/pokemon_clean.parquet` via the project `save_interim()`
helper. This is the input to `03-prepare` (which builds the chart-ready tables).
"""))

cells.append(nbformat.v4.new_code_cell("""\
save_interim(pokemon_clean, cfg, "pokemon_clean.parquet")
"""))

# ── Cell 8 — summary / next ──────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
---
**Next:** `03-prepare.ipynb` — build the chart-ready / analysis-ready tables
(by-type and by-generation stat aggregates, the radar/spider inputs, etc.) from
`pokemon_clean` and export the sellable package.
"""))

# ── Cell 9 — cleanup ─────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
---
## Cleanup
Close the DuckDB connection so the lock is released for other tools (DBCode,
other notebooks). Runs on "Run All".
"""))
cells.append(nbformat.v4.new_code_cell("con.close()\nprint('connection closed')"))

nb.cells = cells

out = Path("notebooks/02-clean.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")
