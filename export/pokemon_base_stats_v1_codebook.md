# pokemon — Dataset Codebook
Generated: 2026-10-05

## Columns

### `species_id`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: National Pokédex number (1..1025); unique per species. The species' dex id as served by PokéAPI.

### `name`
- **Type**: `str`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Species display name, title-cased (e.g. 'Charizard', 'Ho-Oh').

### `generation`
- **Type**: `int32`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Game generation the species debuted in, as an integer 1..9 (Gen I = Red/Blue … Gen IX = Scarlet/Violet).

### `is_legendary`
- **Type**: `bool`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: True if PokéAPI flags the species as Legendary.

### `is_mythical`
- **Type**: `bool`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: True if PokéAPI flags the species as Mythical (event-distributed legendaries).

### `is_legendary_or_mythical`
- **Type**: `bool`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Convenience flag: True if is_legendary OR is_mythical (the 'not an ordinary Pokémon' group used in the legendaries-vs-field comparison).

### `type_1`
- **Type**: `str`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Primary type, title-cased (e.g. 'Fire'). Every species has exactly one primary type.

### `type_2`
- **Type**: `str`
- **Non-null**: 526 / 1,025 (51.3%)
- **Description**: Secondary type, title-cased, or empty/NULL for mono-type species (~499 of 1025).

### `hp`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Base HP stat — current/latest value (health points).

### `attack`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Base Attack stat — current/latest value (physical offense).

### `defense`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Base Defense stat — current/latest value (physical bulk).

### `special_attack`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Base Special Attack stat — current/latest value (special offense).

### `special_defense`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Base Special Defense stat — current/latest value (special bulk).

### `speed`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Base Speed stat — current/latest value (turn order).

### `base_stat_total`
- **Type**: `int64`
- **Non-null**: 1,025 / 1,025 (100.0%)
- **Description**: Sum of the six base stats (hp+attack+defense+special_attack+special_defense+speed); the headline 'BST' power proxy.

## Notes

Source: PokéAPI (https://pokeapi.co/) — keyless public REST API. One row per
Pokémon species across all nine generations (1025 species).
License: PokéAPI data is freely available; Pokémon names/stats are
(c) Nintendo / Game Freak / The Pokemon Company (nominative/fair use, non-commercial).
Scope & method: base stats are the CURRENT / LATEST base stats PokeAPI serves for the
default form of each species (not per-game-era historical values; a handful of stats
have been rebalanced across generations and reflect the latest value). Type_2 is empty
for mono-type species. Generation is the debut generation. This is a fun-tier
pop-culture dataset; see SOURCES.md.
