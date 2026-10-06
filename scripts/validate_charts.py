#!/usr/bin/env python3
"""Pre-publish data-validation GATE — re-check the chart data before anything goes public.

Re-derives the headline facts the four published pokemon radar charts show,
straight from the prepared DuckDB `chart_*` tables, confirms the published
per-species `export/pokemon_base_stats_v1.csv` still matches its DuckDB source
value-for-value, checks the structural invariants (row counts + the normalization
scales), and confirms the social/web PNG sets stay in parity.

The DB is opened **READ-ONLY** (`duckdb.connect(path, read_only=True)`) so this
gate never fights the single-writer lock a notebook or DBCode may hold. It does
not write to the DB, the exports, or the charts.

Exit code 0 = safe to publish. Non-zero = do NOT publish (prints the failing
check).

Usage:
    /opt/anaconda3/envs/data_projects/bin/python scripts/validate_charts.py

Run interpreter: the `data_projects` conda env (has duckdb + pandas + PIL). The
project `.venv` (Py3.14) also has duckdb + pandas + PIL if that env is missing a
dep.
"""
from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd

# --- project bootstrap -------------------------------------------------------
PROJECT = Path(__file__).resolve().parent
while not (PROJECT / "config.yaml").exists() and PROJECT != PROJECT.parent:
    PROJECT = PROJECT.parent
sys.path.insert(0, str(PROJECT))
from src.ingest import load_config  # noqa: E402

failures: list[str] = []
checks: list[str] = []

# The six base stats in the FIXED canonical radar spoke order used everywhere:
#   HP · Attack · Defense · Sp.Atk · Sp.Def · Speed
STATS = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
NORM_COLS = [f"{s}_norm" for s in STATS]
NAVG_COLS = [f"{s}_navg" for s in STATS]

# Normalization denominators (both recomputed/asserted below, never trusted blind):
#   STAT_MAX     = 255   — global max of any individual base stat (Blissey HP);
#                          *_norm = 100 * stat / 255.
#   AVG_STAT_MAX ≈ 111.1 — max averaged stat across the 3 averaged tables
#                          (Steel avg Defense); *_navg = 100 * avg_stat / AVG_STAT_MAX.
STAT_MAX = 255
AVG_STAT_MAX = 111.1

# The three AVERAGED chart tables share the *_navg scale; the iconic table uses *_norm only.
AVG_TABLES = ["chart_type_avg", "chart_generation_avg", "chart_legendary_vs_field"]


def check(name: str, condition: bool, detail: str = "") -> None:
    """Record a PASS/FAIL. `condition` must be truthy to pass."""
    if condition:
        checks.append(f"  PASS  {name}")
    else:
        failures.append(f"  FAIL  {name}" + (f" — {detail}" if detail else ""))


# ---------------------------------------------------------------------------
# Export-vs-DB parity helper
# ---------------------------------------------------------------------------

def _normalize(df: pd.DataFrame, float_round: int = 4) -> pd.DataFrame:
    """Make a frame comparable regardless of int32/int64 and NaN handling.

    - round floats (so DB's higher precision never spuriously differs),
    - render every value as a string with NaN → a stable sentinel,
    so a published CSV (int64 on read) compares equal to a DB frame (int32).
    """
    out = df.copy()
    out = out.reset_index(drop=True)
    for col in out.columns:
        if pd.api.types.is_float_dtype(out[col]):
            out[col] = out[col].round(float_round)
    # Stringify with a NaN sentinel so NaN == NaN compares equal.
    return out.astype(object).where(out.notna(), "<NA>").astype(str)


def assert_csv_matches(name: str, df_db: pd.DataFrame, csv_path: Path) -> None:
    """Assert a published CSV equals the DB-derived frame, value-for-value."""
    if not csv_path.exists():
        check(f"export parity: {name} (file present)", False, f"missing {csv_path}")
        return
    df_csv = pd.read_csv(csv_path)
    check(f"export parity: {name} row count", len(df_csv) == len(df_db),
          f"csv={len(df_csv)} db={len(df_db)}")
    check(f"export parity: {name} columns",
          list(df_csv.columns) == list(df_db.columns),
          f"csv={list(df_csv.columns)} db={list(df_db.columns)}")
    if list(df_csv.columns) != list(df_db.columns) or len(df_csv) != len(df_db):
        return
    norm_csv = _normalize(df_csv)
    norm_db = _normalize(df_db[df_csv.columns])
    # Order-insensitive content comparison: sort both by all columns before
    # comparing so a tie-order flip can't false-fail; every value and the full
    # row set must still match.
    cols = list(norm_csv.columns)
    norm_csv_s = norm_csv.sort_values(cols).reset_index(drop=True)
    norm_db_s = norm_db.sort_values(cols).reset_index(drop=True)
    equal = norm_csv_s.equals(norm_db_s)
    detail = ""
    if not equal:
        diff_mask = norm_csv_s.ne(norm_db_s)
        where = diff_mask.stack()
        first = where[where].index[:1].tolist()
        detail = f"first diff at {first}" if first else "value mismatch"
    check(f"export parity: {name} values match DB", equal, detail)


# ---------------------------------------------------------------------------
# Check groups
# ---------------------------------------------------------------------------

def check_structural(con: duckdb.DuckDBPyConnection) -> None:
    """(c) STRUCTURAL — prepared-table row counts, column sets, no NULLs."""
    expected_rows = {
        "chart_iconic_fingerprints": 12,
        "chart_type_avg": 18,
        "chart_generation_avg": 9,
        "chart_legendary_vs_field": 2,
    }
    for tbl, n in expected_rows.items():
        got = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        check(f"structural: {tbl} = {n} rows (non-zero)", got == n and got > 0,
              f"got {got}")

    # Column-set invariants: iconic carries *_norm but NOT *_navg; the three
    # averaged tables carry *_navg.
    iconic_cols = [r[0] for r in con.execute("DESCRIBE chart_iconic_fingerprints").fetchall()]
    check("structural: iconic has all 6 *_norm cols",
          all(c in iconic_cols for c in NORM_COLS),
          f"got {iconic_cols}")
    check("structural: iconic has NO *_navg cols",
          not any(c.endswith("_navg") for c in iconic_cols),
          f"got {[c for c in iconic_cols if c.endswith('_navg')]}")
    for tbl in AVG_TABLES:
        cols = [r[0] for r in con.execute(f"DESCRIBE {tbl}").fetchall()]
        check(f"structural: {tbl} has all 6 *_navg cols",
              all(c in cols for c in NAVG_COLS), f"got {cols}")

    # No NULLs in the asserted stat / normalized columns.
    null_cols = {
        "chart_iconic_fingerprints": STATS + NORM_COLS,
        "chart_type_avg": STATS + NORM_COLS + NAVG_COLS,
        "chart_generation_avg": STATS + NORM_COLS + NAVG_COLS + ["avg_base_stat_total"],
        "chart_legendary_vs_field": STATS + NORM_COLS + NAVG_COLS + ["avg_base_stat_total"],
    }
    for tbl, cols in null_cols.items():
        where = " OR ".join(f"{c} IS NULL" for c in cols)
        n_null = con.execute(f"SELECT COUNT(*) FROM {tbl} WHERE {where}").fetchone()[0]
        check(f"structural: no NULLs in {tbl} stat/_norm/_navg cols", n_null == 0,
              f"{n_null} row(s) with a null")

    # Coverage sums.
    check("structural: chart_type_avg.n_species sums to 1025",
          con.execute("SELECT SUM(n_species) FROM chart_type_avg").fetchone()[0] == 1025)
    check("structural: chart_legendary_vs_field.n_species sums to 1025",
          con.execute("SELECT SUM(n_species) FROM chart_legendary_vs_field").fetchone()[0] == 1025)
    gen_counts = dict(con.execute(
        "SELECT generation, n_species FROM chart_generation_avg ORDER BY generation").fetchall())
    expected_gen = {1: 151, 2: 100, 3: 135, 4: 107, 5: 156, 6: 72, 7: 88, 8: 96, 9: 120}
    check("structural: chart_generation_avg per-gen n_species match known counts",
          gen_counts == expected_gen, f"got {gen_counts}")


def check_upstream(con: duckdb.DuckDBPyConnection) -> None:
    """(c) UPSTREAM sanity — pokemon_clean integrity feeding every chart table."""
    n = con.execute("SELECT COUNT(*) FROM pokemon_clean").fetchone()[0]
    check("upstream: pokemon_clean = 1025 rows", n == 1025, f"got {n}")

    gmin, gmax = con.execute(
        "SELECT MIN(generation), MAX(generation) FROM pokemon_clean").fetchone()
    check("upstream: generation INT within 1..9", gmin == 1 and gmax == 9,
          f"got [{gmin}, {gmax}]")

    mismatch = con.execute(
        "SELECT COUNT(*) FROM pokemon_clean "
        "WHERE base_stat_total <> hp+attack+defense+special_attack+special_defense+speed"
    ).fetchone()[0]
    check("upstream: base_stat_total == sum of the 6 stats (0 mismatches)",
          mismatch == 0, f"{mismatch} mismatch(es)")

    bmin, bmax = con.execute(
        "SELECT MIN(base_stat_total), MAX(base_stat_total) FROM pokemon_clean").fetchone()
    check("upstream: base_stat_total range 175..720", bmin == 175 and bmax == 720,
          f"got [{bmin}, {bmax}]")

    # The 255 individual-max denominator must still hold (Blissey HP).
    stat_max = con.execute(
        "SELECT GREATEST(MAX(hp), MAX(attack), MAX(defense), "
        "MAX(special_attack), MAX(special_defense), MAX(speed)) FROM pokemon_clean"
    ).fetchone()[0]
    check(f"upstream: STAT_MAX == {STAT_MAX} (global individual max)",
          stat_max == STAT_MAX, f"got {stat_max}")


def check_normalization(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Normalization sanity — every *_norm/_navg in 0..100; one shared ~100 max."""
    # *_norm within 0..100 across all four tables.
    for tbl in ["chart_iconic_fingerprints"] + AVG_TABLES:
        bounds = ", ".join(f"MIN({c}), MAX({c})" for c in NORM_COLS)
        vals = con.execute(f"SELECT {bounds} FROM {tbl}").fetchone()
        lo, hi = min(vals[::2]), max(vals[1::2])
        check(f"normalization: {tbl} *_norm within 0..100", 0 <= lo and hi <= 100,
              f"got [{lo}, {hi}]")

    # *_navg within 0..100 across the three averaged tables; track the global max.
    global_navg_max = 0.0
    for tbl in AVG_TABLES:
        bounds = ", ".join(f"MIN({c}), MAX({c})" for c in NAVG_COLS)
        vals = con.execute(f"SELECT {bounds} FROM {tbl}").fetchone()
        lo, hi = min(vals[::2]), max(vals[1::2])
        check(f"normalization: {tbl} *_navg within 0..100", 0 <= lo and hi <= 100,
              f"got [{lo}, {hi}]")
        global_navg_max = max(global_navg_max, hi)

    # The single max *_navg across the three averaged tables must reach ~100
    # (Steel defense_navg), confirming the shared averaged denominator.
    check("normalization: max *_navg across averaged tables ~= 100 (shared denom)",
          abs(global_navg_max - 100.0) < 0.5, f"got {global_navg_max}")


def check_chart04_types(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 4 — Steel is the defensive type: max avg Defense ~= 111.1."""
    top_type, top_def = con.execute(
        "SELECT type_1, defense FROM chart_type_avg ORDER BY defense DESC LIMIT 1"
    ).fetchone()
    check("chart04: Steel is the max-avg-Defense primary type", top_type == "Steel",
          f"got {top_type!r}")
    check("chart04: Steel avg Defense ~= 111.1 (= AVG_STAT_MAX; tol 0.5)",
          abs(top_def - AVG_STAT_MAX) <= 0.5, f"got {top_def}")

    steel_navg = con.execute(
        "SELECT defense_navg FROM chart_type_avg WHERE type_1 = 'Steel'"
    ).fetchone()[0]
    check("chart04: Steel defense_navg ~= 100 (tol 0.5)",
          abs(steel_navg - 100.0) <= 0.5, f"got {steel_navg}")


def check_chart03_generations(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 3 — power creep: Gen 9 has max avg BST ~= 457.4; early gens lower."""
    top_gen, top_bst = con.execute(
        "SELECT generation, avg_base_stat_total FROM chart_generation_avg "
        "ORDER BY avg_base_stat_total DESC LIMIT 1"
    ).fetchone()
    check("chart03: Gen 9 has the max avg base-stat-total", top_gen == 9,
          f"got gen {top_gen}")
    check("chart03: Gen 9 avg BST ~= 457.4 (tol 1.0)", abs(top_bst - 457.4) <= 1.0,
          f"got {top_bst}")

    gen1_bst = con.execute(
        "SELECT avg_base_stat_total FROM chart_generation_avg WHERE generation = 1"
    ).fetchone()[0]
    check("chart03: Gen 1 avg BST within 403..408 (power creep is up)",
          403.0 <= gen1_bst <= 408.0, f"got {gen1_bst}")


def check_chart02_legendary(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 2 — legendaries outside the field on every axis; BST ~592 vs ~411."""
    rows = {g: dict(zip(["n"] + STATS + ["bst"], rest)) for g, *rest in con.execute(
        "SELECT group_name, n_species, hp, attack, defense, special_attack, "
        "special_defense, speed, avg_base_stat_total FROM chart_legendary_vs_field"
    ).fetchall()}
    leg = rows.get("Legendary/Mythical")
    field = rows.get("Field")
    check("chart02: both groups present (Legendary/Mythical + Field)",
          leg is not None and field is not None, f"got {list(rows)}")
    if leg is None or field is None:
        return

    check("chart02: group counts legendary=94, field=931",
          leg["n"] == 94 and field["n"] == 931, f"leg={leg['n']} field={field['n']}")
    check("chart02: group counts sum to 1025", leg["n"] + field["n"] == 1025,
          f"sum={leg['n'] + field['n']}")
    check("chart02: legendary avg BST ~= 592 (tol 2.0)", abs(leg["bst"] - 592.0) <= 2.0,
          f"got {leg['bst']}")
    check("chart02: field avg BST ~= 411 (tol 2.0)", abs(field["bst"] - 411.0) <= 2.0,
          f"got {field['bst']}")

    # The 'outside on every axis' claim — legendary > field on EACH of the 6 stats.
    for s in STATS:
        check(f"chart02: legendary avg {s} > field avg {s}", leg[s] > field[s],
              f"leg={leg[s]} field={field[s]}")


def check_chart01_iconic(con: duckdb.DuckDBPyConnection) -> None:
    """(b) Chart 1 — the 12 icons present + robust shape spot-checks (argmax within 12)."""
    names = {r[0] for r in con.execute(
        "SELECT name FROM chart_iconic_fingerprints").fetchall()}
    expected = {
        "Pikachu", "Charizard", "Blastoise", "Alakazam", "Machamp", "Gyarados",
        "Snorlax", "Dragonite", "Steelix", "Shuckle", "Gardevoir", "Garchomp",
    }
    check("chart01: all 12 iconic names present", names == expected,
          f"missing={expected - names}; extra={names - expected}")

    # Shuckle = the wall: max (defense + special_defense) among the 12, and a low speed.
    wall_top = con.execute(
        "SELECT name FROM chart_iconic_fingerprints "
        "ORDER BY (defense + special_defense) DESC LIMIT 1"
    ).fetchone()[0]
    check("chart01: Shuckle is the max (Def+SpDef) wall among the 12",
          wall_top == "Shuckle", f"got {wall_top!r}")
    shuckle_speed = con.execute(
        "SELECT speed FROM chart_iconic_fingerprints WHERE name = 'Shuckle'"
    ).fetchone()[0]
    check("chart01: Shuckle has a low speed (<30, a wall)", shuckle_speed < 30,
          f"got {shuckle_speed}")

    # Alakazam = the glass cannon: max (special_attack + speed) among the 12, low defense.
    cannon_top = con.execute(
        "SELECT name FROM chart_iconic_fingerprints "
        "ORDER BY (special_attack + speed) DESC LIMIT 1"
    ).fetchone()[0]
    check("chart01: Alakazam is the max (SpAtk+Speed) glass cannon among the 12",
          cannon_top == "Alakazam", f"got {cannon_top!r}")
    alakazam_def = con.execute(
        "SELECT defense FROM chart_iconic_fingerprints WHERE name = 'Alakazam'"
    ).fetchone()[0]
    check("chart01: Alakazam has a low defense (<60, glass cannon)", alakazam_def < 60,
          f"got {alakazam_def}")


def check_export_parity(con: duckdb.DuckDBPyConnection) -> None:
    """(a) EXPORT-vs-DB parity — the per-species CSV matches its DB source frame.

    Re-derives the exact SELECT 03-prepare used to build the export (per-species
    from pokemon_clean, ORDER BY species_id) and compares value-for-value.
    """
    export_dir = PROJECT / "export"
    export_db = con.execute("""
        SELECT
            species_id, name, generation,
            is_legendary, is_mythical, is_legendary_or_mythical,
            type_1, type_2,
            hp, attack, defense, special_attack, special_defense, speed,
            base_stat_total
        FROM pokemon_clean
        ORDER BY species_id
    """).df()
    check("export parity: DB-derived per-species frame = 1025 rows",
          len(export_db) == 1025, f"got {len(export_db)}")
    assert_csv_matches("pokemon_base_stats_v1", export_db,
                       export_dir / "pokemon_base_stats_v1.csv")


def check_png_parity() -> None:
    """(d) SOCIAL/WEB PARITY — the 4 named lineup charts; social 1600x900, web 1664w.

    Ignores the stale 04-viz exploratory PNGs (02a_type_avg_facet,
    02b_steel_vs_frail_overlay, 04_legendary_vs_field_overlay) — only the four
    named published charts are asserted.
    """
    expected_stems = {
        "01_iconic_fingerprints_facet",
        "02_legendary_vs_field_overlay",
        "03_generation_power_creep_facet",
        "04_steel_electric_normal_overlay",
    }
    social_dir = PROJECT / "outputs" / "social"
    web_dir = PROJECT / "outputs" / "web"

    social = {p.stem: p for p in social_dir.glob("*.png")}
    web = {p.stem: p for p in web_dir.glob("*.png")}

    # Only the four named lineup charts matter; stale exploratory PNGs are ignored.
    check("png parity: social has the 4 named lineup charts",
          expected_stems <= set(social),
          f"missing from social: {sorted(expected_stems - set(social))}")
    check("png parity: web has the 4 named lineup charts",
          expected_stems <= set(web),
          f"missing from web: {sorted(expected_stems - set(web))}")

    try:
        from PIL import Image
    except ImportError:
        check("png parity: PIL available for dimension check", False,
              "Pillow not importable")
        return

    # Social: exactly 1600x900. Web: width must be 1664 (a facet may run taller).
    for stem in sorted(expected_stems):
        if stem in social:
            size = Image.open(social[stem]).size
            check(f"png parity: social {stem} is 1600x900", size == (1600, 900),
                  f"got {size}")
        if stem in web:
            w, h = Image.open(web[stem]).size
            check(f"png parity: web {stem} width is 1664", w == 1664, f"got {(w, h)}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    cfg = load_config(str(PROJECT / "config.yaml"))
    db = str(PROJECT / cfg["settings"]["duckdb_file"])
    con = duckdb.connect(db, read_only=True)  # READ-ONLY — never fight the writer lock
    try:
        check_structural(con)
        check_upstream(con)
        check_normalization(con)
        check_chart04_types(con)
        check_chart03_generations(con)
        check_chart02_legendary(con)
        check_chart01_iconic(con)
        check_export_parity(con)
    finally:
        con.close()

    # PNG parity doesn't need the DB.
    check_png_parity()

    print("Pre-publish chart-data validation — pokemon")
    print("=" * 64)
    for line in checks:
        print(line)
    for line in failures:
        print(line)
    print("=" * 64)
    if failures:
        print(f"RESULT: {len(failures)} FAILURE(S) of {len(checks)+len(failures)} checks "
              f"— DO NOT PUBLISH.")
        return 1
    print(f"RESULT: all {len(checks)} checks passed — safe to publish.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
