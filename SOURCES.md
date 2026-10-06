# Data Sources — pokemon

Source standards are **tiered**:
- **Serious tier** (methodology invites scrutiny): use official government or
  authoritative primary sources only. Crowd-edited references (Wikipedia, etc.)
  are NOT used — credibility is the product.
- **Fun tier** (low-stakes pop-culture): crowd-sourced references (fan wikis,
  SuperSummary, etc.) and owner-as-primary (hand-collected counts from a book or
  broadcast) are fine — just cite them plainly below.

Document every data source here before ingesting it. Include enough detail
that someone else could independently locate and verify the original data.

---

## Source Template

Copy and fill in for each source. The **How the source collects the data**,
**How the source defines the data**, and **Methodology changes / series breaks**
sections are required — they are what keep our analysis honest and prevent
apples-to-oranges comparisons. Do not leave them blank; if something is genuinely
not applicable or unknown, write "N/A" or "unknown" so it's clear it was considered.

### [Source Name]
- **Publisher:** [Agency, organization, or author]
- **URL:** [Direct link to the file or page]
- **Format:** [CSV | JSON | HTML table | ZIP | PDF | hand-curated]
- **License:** [Public domain | CC0 | CC-BY | proprietary | etc.]
- **Fields used:** [Column names or description of what was extracted]
- **Coverage:** [Geographic scope, date range, or other relevant bounds]
- **How the source collects the data:** [How does the publisher actually gather it?
  Survey / administrative records / registration / model estimate / scraped, etc.
  For surveys: sampling frame, sample size, response rate. For counts: the universe
  and denominator. Who is included and who is excluded from the raw collection?]
- **How the source defines the data:** [How is the thing being measured *defined*?
  Spell out the judgment calls in what counts. Example: a "COVID death" can mean died
  *from* COVID (underlying cause) vs. died *with* COVID (contributing/any mention) —
  very different counts. Note the exact definition this source uses.]
- **Methodology changes / series breaks:** [Dates when the definition or collection
  method changed, and which time periods are therefore NOT directly comparable.
  If the whole series is consistent, say so explicitly. This is the flag that stops
  us from charting a pre-change number next to a post-change number as if they match.]
- **Known controversies / debates:** [Any contested measurement choices worth a
  footnote or caveat in a published chart. Optional but encouraged. "None known" is
  a valid answer once you've checked.]
- **Notes:** [Anything else — data-quality quirks, suppression rules, imputation, etc.]
- **Retrieved:** [YYYY-MM-DD]

---

## Sources

### PokéAPI
- **Publisher:** PokéAPI (pokeapi.co) — a community-run, open REST API of Pokémon game data.
- **URL:** https://pokeapi.co/api/v2 (endpoints `/pokemon-species`, `/pokemon-species/{id}`, `/pokemon/{id}`)
- **Format:** JSON REST API (keyless, public). Pulled per-species and cached verbatim at retrieval, then transcribed one row per species.
- **License:** PokéAPI data is freely available for use. Pokémon names, stats, and
  types are © Nintendo / Game Freak / The Pokémon Company — used here nominatively
  (fun-tier, non-commercial, attributed).
- **Fields used:** per species — base stats (HP, Attack, Defense, Sp. Atk, Sp. Def,
  Speed), primary/secondary type, generation, legendary/mythical flags.
- **Coverage:** all 9 generations, National Dex species 1–1025. Retrieved 2026-10-05.
- **How the source collects the data:** PokéAPI transcribes the official game data
  (current/latest generation values) from the Pokémon video games into a structured
  API. It is a faithful mirror of game stats, not a survey or estimate.
- **How the source defines the data:** "base stats" are the per-species base values
  used by the games' stat formulas (0–255 per stat). We take the **default variety**
  of each species (`is_default` form) — i.e. the canonical base form.
- **⭐ Scope decision (the load-bearing caveat — carry into chart captions):**
  **Base forms only.** We use one canonical default-form row per species (1025 total);
  **alternate forms, Mega Evolutions, Gigantamax, regional variants, and Paradox forms
  are EXCLUDED** (~326 non-default `/pokemon` entries dropped). Consequently our
  *averages* run slightly below form-inclusive community encyclopedias: e.g. the
  Legendary/Mythical average base-stat total is ~592 here vs ~626 on Bulbapedia (which
  includes high-stat Mega/alternate legendary forms), and Steel's average Defense is
  ~111 here vs ~109–110 elsewhere depending on form inclusion. These are **scope
  differences, not errors** — the rankings and directional claims (Steel = highest
  Defense; legendaries exceed the field on every axis; Gen 9 highest average total)
  hold either way. Any published averaged chart states: *"Base forms only; averages
  exclude megas & alternate forms."*
- **Methodology changes / series breaks:** base stats were rebalanced for some species
  in Gen VI (the "Pokémon Bank" era, e.g. several Normal-types gained stats). PokéAPI
  reflects **current/latest** values, not per-game historical values — so a
  cross-generation comparison here compares species by their *current* stats, not the
  stats as they shipped in each era. Documented; acceptable for a current-snapshot
  analysis.
- **Known controversies / debates:** "legendary vs mythical" classification and what
  counts as a distinct species vs a form are community/publisher conventions with
  edge cases (Ultra Beasts, Paradox forms, convergent species). We follow PokéAPI's
  `is_legendary`/`is_mythical` flags and default-variety definition.
- **Notes:** independent cross-checks (PokemonDB, Bulbapedia, PokemonRef, et al.)
  confirmed the counts (94 legendary/mythical, 931 field) and the structural claims.
- **Retrieved:** 2026-10-05

<!-- Add additional sources below this line -->

---

## Notes on Data Quality

- Source responses are preserved verbatim at retrieval and never modified.
- Discrepancies between sources should be noted here and resolved explicitly.
- **Series breaks:** whenever a source changed its definition or method mid-series,
  document the break date under that source and treat pre/post as separate series —
  never chart or aggregate across a break without a visible caveat.
- **Definitions drive comparisons:** before comparing two numbers (across years,
  places, or sources), confirm they are defined the same way. If not, say so in the
  chart, the codebook, and any social copy.


