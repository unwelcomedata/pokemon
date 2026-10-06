"""Build 01-ingest.ipynb for the pokemon project.

Regenerate with:  .venv/bin/python scripts/_build_nb_01_ingest.py
Then execute with: .venv/bin/python -m jupyter nbconvert --to notebook \
    --execute --inplace --ExecutePreprocessor.timeout=3600 notebooks/01-ingest.ipynb
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
# 01 — Ingest: PokéAPI base stats

Fetches Pokémon base-stat data for **all 9 generations** from PokéAPI and lands
it in `data/raw/` (untouched raw JSON) and `data/project.duckdb`.

**No transformation happens here** — values land in DuckDB exactly as the API
returns them. All cleaning is in `02-clean.ipynb`.
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

from src.ingest import load_config, ingest_pokeapi
from src.clean_quality import get_connection, load_to_duckdb, register_source
import pandas as pd

cfg = load_config("config.yaml")
con = get_connection(cfg)
print(f"Project: {cfg['project_name']}")
"""))

# ── Cell 2 — source section ─────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Source: PokéAPI (keyless public REST API)

Source: **[PokéAPI](https://pokeapi.co/)** — a free, keyless, public REST API
serving the canonical Pokémon game data (base stats, types, species metadata).
No account or API key is required.

**Cloudflare 403 gotcha.** PokéAPI is fronted by Cloudflare, which returns
**HTTP 403** to the default Python/urllib user-agent. Every request therefore
sends a **browser User-Agent** (from `src/ingest._DEFAULT_HEADERS`); with that
header the requests succeed.

**Scope: all 9 generations, default species form only.**
- `GET /pokemon-species?limit=100000` reports **1025 species** across
  `generation-i` … `generation-ix`.
- There are ~1351 `/pokemon` entries vs 1025 species — the extra ~326 are
  **alternate forms** (Mega / Gigantamax / regional variants). We pull **one
  canonical row per species**: the species' *default* variety (`is_default`
  True), where the base stats live. Alternate forms are **excluded** from the
  raw table (the default form's raw JSON is what we cache).

**Caching.** Every raw response is cached to `data/raw/` —
`data/raw/species/{id}.json` and `data/raw/pokemon/{id}.json`, plus the species
listing — and any file already on disk is **skipped**, so the pull is resumable
and re-execution is instant. This respects PokéAPI's ask to cache aggressively.

**Rate limit for this bulk pull.** The config's polite delay is 1.5s, but
1025 species × 2 calls at 1.5s is ~50 min. For this single bulk pull we use a
lighter-but-still-polite **0.4s** delay between *network* calls (cache hits
incur no delay), as a single-threaded, well-behaved client. The cache makes
every later re-run free regardless of the delay.
"""))

# ── Cell 3 — run the ingest ─────────────────────────────────────────────────
cells.append(nbformat.v4.new_code_cell("""\
# Walk all 1025 species (species JSON + default-variety pokemon JSON), caching
# every raw response to data/raw/. 0.4s delay on network calls only.
df = ingest_pokeapi(cfg, rate_limit_seconds=0.4)
print()
print("df.shape:", df.shape)
df.head()
"""))

# ── Cell 4 — generation coverage ────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Confirm all 9 generations landed
"""))

cells.append(nbformat.v4.new_code_cell("""\
# One count per generation — should span generation-i through generation-ix.
df["generation"].value_counts().sort_index()
"""))

# ── Cell 5 — load into DuckDB ────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Load into DuckDB as `pokemon_raw`

One canonical row per species. Values are untransformed (still "raw"); the only
derived field is `base_stat_total`, the sum of the six base stats.
"""))

cells.append(nbformat.v4.new_code_cell("""\
load_to_duckdb(df, "pokemon_raw", con)
n = con.execute("SELECT COUNT(*) FROM pokemon_raw").fetchone()[0]
print(f"pokemon_raw: {n:,} rows loaded into DuckDB")

register_source(
    con,
    "pokemon_raw",
    "PokéAPI",
    url="https://pokeapi.co/api/v2",
    license=cfg["sources"]["pokeapi"]["license"],
    notes=(
        "All 9 generations, default species form only (~326 alt forms excluded); "
        "base stats + types + generation + legendary/mythical flags"
    ),
    retrieved="2026-10-05",
    methodology=(
        "Per-species default-variety base stats from /pokemon/{id}; generation + "
        "legendary/mythical from /pokemon-species/{id}"
    ),
    series_breaks=(
        "Base-stat values were rebalanced in Gen VI for some species (e.g. "
        "Pokémon Bank era); PokéAPI reflects current/latest stats, not historical "
        "per-game values"
    ),
)
print("Source registered in _sources.")
"""))

# ── Cell 6 — quick inspection ───────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
## Quick inspection
"""))

cells.append(nbformat.v4.new_code_cell("""\
# Base-stat-total range and a legendary/mythical count — a plausibility check.
print(con.execute(\"\"\"
    SELECT COUNT(*) AS n_species,
           COUNT(DISTINCT generation) AS n_generations,
           MIN(base_stat_total) AS min_bst,
           MAX(base_stat_total) AS max_bst,
           SUM(CAST(is_legendary AS INT)) AS n_legendary,
           SUM(CAST(is_mythical AS INT)) AS n_mythical
    FROM pokemon_raw
\"\"\").df().to_string(index=False))
"""))

# ── Cell 7 — summary / next ─────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
---
**Next:** `02-clean.ipynb` — load `pokemon_raw` into interim, run quality
checks, and shape the per-Pokémon / per-type / per-generation stat tables.
"""))

# ── Cell 8 — cleanup ────────────────────────────────────────────────────────
cells.append(nbformat.v4.new_markdown_cell("""\
---
## Cleanup
Close the DuckDB connection so the lock is released for other tools (DBCode,
other notebooks). Runs on "Run All".
"""))
cells.append(nbformat.v4.new_code_cell("con.close()\nprint('connection closed')"))

nb.cells = cells

out = Path("notebooks/01-ingest.ipynb")
nbformat.write(nb, out)
print(f"Written: {out}")
