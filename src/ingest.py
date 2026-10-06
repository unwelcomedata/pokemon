"""Web ingestion utilities.

Handles three source types:
  - html_table  : pandas read_html on a static page
  - html_scrape : BeautifulSoup for custom element extraction
  - csv / json  : direct download and save to data/raw

All raw files land in data/raw unchanged. Call load_config() once per notebook
to get paths and source definitions from config.yaml.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import yaml
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load project config.yaml and return it as a dict."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def raw_path(cfg: dict, filename: str) -> Path:
    """Return a Path inside data/raw, creating the directory if needed."""
    p = Path(cfg["paths"]["data_raw"]) / filename
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_CACHE_DIR: Path | None = None


def _get_cache_dir(cfg: dict) -> Path:
    """Return the cache directory (data/raw by default)."""
    global _CACHE_DIR
    if _CACHE_DIR is None:
        _CACHE_DIR = Path(cfg["paths"]["data_raw"])
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR


def fetch_html(url: str, headers: dict | None = None, timeout: int = 30) -> str:
    """Fetch a URL and return the response text.

    Raises requests.HTTPError on non-2xx status.
    """
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    resp = requests.get(url, headers=hdrs, timeout=timeout)
    resp.raise_for_status()
    return resp.text


def fetch_cached(
    url: str,
    filename: str,
    cfg: dict,
    max_age_hours: float = 24.0,
    headers: dict | None = None,
    timeout: int = 30,
) -> str:
    """Fetch a URL with local file caching.

    If a cached file exists and is younger than max_age_hours, returns its
    contents without making a network request. Otherwise fetches, saves to
    data/raw/{filename}, and returns the content.

    Args:
        url:            URL to fetch.
        filename:       Cache filename (saved in data/raw/).
        cfg:            Loaded config dict.
        max_age_hours:  Re-fetch if cache is older than this (0 = always fetch).
        headers:        Optional extra HTTP headers.
        timeout:        Request timeout in seconds.

    Returns:
        Response text (from cache or network).
    """
    cache_path = _get_cache_dir(cfg) / filename
    if cache_path.exists() and max_age_hours > 0:
        age_hours = (time.time() - cache_path.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return cache_path.read_text(encoding="utf-8")

    text = fetch_html(url, headers=headers, timeout=timeout)
    cache_path.write_text(text, encoding="utf-8")
    return text


def fetch_with_retry(
    url: str,
    headers: dict | None = None,
    timeout: int = 30,
    max_retries: int = 3,
    rate_limit_seconds: float = 1.5,
) -> str:
    """Fetch a URL with rate limiting and exponential backoff on 429s.

    Args:
        url:                 URL to fetch.
        headers:             Optional extra HTTP headers.
        timeout:             Request timeout in seconds.
        max_retries:         Max retry attempts on 429/5xx.
        rate_limit_seconds:  Minimum delay between requests.

    Returns:
        Response text.

    Raises:
        requests.HTTPError after exhausting retries.
    """
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    time.sleep(rate_limit_seconds)

    for attempt in range(max_retries + 1):
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < max_retries:
                wait = rate_limit_seconds * (2 ** attempt)
                print(f"  ⚠ {resp.status_code} on {url} — retrying in {wait:.0f}s")
                time.sleep(wait)
                continue
        resp.raise_for_status()
        return resp.text

    resp.raise_for_status()  # will raise on the last failed attempt
    return ""  # unreachable


def fetch_html_js(url: str, wait_selector: str | None = None, timeout: int = 30000) -> str:
    """Fetch a JS-rendered page using Playwright (headless Chromium).

    Use this when fetch_html() returns an empty or incomplete page.
    Requires: playwright install chromium

    Args:
        url:           Page URL.
        wait_selector: Optional CSS selector to wait for before returning HTML.
        timeout:       Playwright timeout in milliseconds.
    """
    from playwright.sync_api import sync_playwright  # lazy import

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(extra_http_headers=_DEFAULT_HEADERS)
        page.goto(url, timeout=timeout)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=timeout)
        else:
            page.wait_for_load_state("networkidle", timeout=timeout)
        html = page.content()
        browser.close()
    return html


# ---------------------------------------------------------------------------
# Parsers
# ---------------------------------------------------------------------------

def parse_html_table(html: str, table_index: int = 0) -> pd.DataFrame:
    """Extract a <table> from HTML by index and return it as a DataFrame.

    Cleans up column names: lowercase, spaces → underscores.

    Note: pandas 3.x no longer accepts a raw HTML *string* — it must be a
    file-like object — so the string is wrapped in StringIO.
    """
    from io import StringIO

    tables = pd.read_html(StringIO(html))
    if not tables:
        raise ValueError("No tables found in the provided HTML.")
    if table_index >= len(tables):
        raise IndexError(
            f"table_index {table_index} out of range — page has {len(tables)} table(s)."
        )
    df = tables[table_index]
    df.columns = [
        str(c).strip().lower().replace(" ", "_").replace("-", "_")
        for c in df.columns
    ]
    return df


def parse_html_scrape(
    html: str,
    row_selector: str,
    field_map: dict[str, str],
) -> pd.DataFrame:
    """Scrape structured rows from HTML using CSS selectors.

    Args:
        html:          Raw HTML string.
        row_selector:  CSS selector that matches each "row" element.
        field_map:     Dict mapping output column name → CSS selector
                       relative to each row element.
                       Use '' (empty string) to get the row's own text.

    Example:
        parse_html_scrape(html, "tr.data-row", {"name": "td.name", "value": "td.val"})
    """
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select(row_selector)
    records = []
    for row in rows:
        record: dict[str, str] = {}
        for col, selector in field_map.items():
            el = row.select_one(selector) if selector else row
            record[col] = el.get_text(" ", strip=True) if el else ""
        records.append(record)
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def download_file(url: str, dest: Path, headers: dict | None = None, timeout: int = 60) -> Path:
    """Stream-download a file (CSV, JSON, zip, etc.) to dest and return the path."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    with requests.get(url, headers=hdrs, timeout=timeout, stream=True) as resp:
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
    return dest


# ---------------------------------------------------------------------------
# Source-driven ingest (reads config.yaml sources block)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PokéAPI ingest (keyless public REST API)
# ---------------------------------------------------------------------------

# The six base stats, in the consistent order PokéAPI returns them, mapped to
# the snake_case column names used in the raw table.
_POKEAPI_STAT_COLUMNS: dict[str, str] = {
    "hp": "hp",
    "attack": "attack",
    "defense": "defense",
    "special-attack": "special_attack",
    "special-defense": "special_defense",
    "speed": "speed",
}


def _fetch_json_cached(
    url: str,
    cache_file: Path,
    headers: dict | None = None,
    timeout: int = 30,
    max_retries: int = 4,
    rate_limit_seconds: float = 0.4,
) -> dict[str, Any]:
    """Fetch a JSON URL, caching the raw response to ``cache_file``.

    If ``cache_file`` already exists it is read straight from disk with no
    network call (the pull is resumable and re-runs are free). On a cache miss
    the function sleeps ``rate_limit_seconds`` before hitting the network and
    retries with exponential backoff on 429/5xx responses.

    PokéAPI is Cloudflare-fronted and returns HTTP 403 to the default
    Python/urllib user-agent, so a browser User-Agent (``_DEFAULT_HEADERS``)
    is always sent.

    Returns the parsed JSON as a dict.
    """
    if cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    hdrs = {**_DEFAULT_HEADERS, **(headers or {})}
    time.sleep(rate_limit_seconds)

    for attempt in range(max_retries + 1):
        resp = requests.get(url, headers=hdrs, timeout=timeout)
        if resp.status_code == 429 or resp.status_code >= 500:
            if attempt < max_retries:
                wait = rate_limit_seconds * (2 ** attempt)
                print(f"  ⚠ {resp.status_code} on {url} — retrying in {wait:.1f}s")
                time.sleep(wait)
                continue
        resp.raise_for_status()
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(resp.text, encoding="utf-8")
        return resp.json()

    resp.raise_for_status()  # exhausted retries — raise the last error
    return {}  # unreachable


def ingest_pokeapi(
    cfg: dict,
    rate_limit_seconds: float | None = None,
    progress_every: int = 100,
) -> pd.DataFrame:
    """Ingest base-stat data for all Pokémon species from PokéAPI.

    Walks every species (all 9 generations, ~1025 species). For each species it
    fetches the species JSON (``/pokemon-species/{id}``) and the species'
    *default* variety pokemon JSON (``/pokemon/{id}``, where base stats live).
    Alternate forms (Mega/Gigantamax/regional) are intentionally excluded — one
    canonical row per species.

    Every raw response is cached to ``data/raw/species/{id}.json`` and
    ``data/raw/pokemon/{id}.json`` and skipped on re-runs, so the pull is
    resumable and re-execution is instant (PokéAPI asks clients to cache
    aggressively). The polite delay only applies on actual network calls.

    This assembles the untransformed API JSON into a tidy table; it does not
    clean or derive anything beyond summing the six base stats — all real
    cleaning belongs in ``02-clean``.

    Args:
        cfg:                 Loaded config dict (from ``load_config()``).
        rate_limit_seconds:  Delay between network calls. Defaults to the
                             ``sources.pokeapi.rate_limit_seconds`` config value.
        progress_every:      Print progress every N species.

    Returns:
        One row per species with columns: ``species_id``, ``name``,
        ``generation``, ``is_legendary``, ``is_mythical``, ``type_1``,
        ``type_2``, ``hp``, ``attack``, ``defense``, ``special_attack``,
        ``special_defense``, ``speed``, ``base_stat_total``.
    """
    source = cfg["sources"]["pokeapi"]
    base_url: str = source["base_url"].rstrip("/")
    if rate_limit_seconds is None:
        rate_limit_seconds = float(source.get("rate_limit_seconds", 1.5))

    raw_dir = Path(cfg["paths"]["data_raw"])
    species_dir = raw_dir / "species"
    pokemon_dir = raw_dir / "pokemon"

    # Full species list (name + detail URL). Cached like everything else.
    listing = _fetch_json_cached(
        f"{base_url}/pokemon-species?limit=100000",
        raw_dir / "pokemon-species-list.json",
        rate_limit_seconds=rate_limit_seconds,
    )
    results = listing["results"]
    total = len(results)
    print(f"PokéAPI: {total} species to ingest (rate limit {rate_limit_seconds}s on network calls)")

    records: list[dict[str, Any]] = []
    for i, entry in enumerate(results, start=1):
        # The species id is the trailing path segment of its detail URL.
        species_id = int(entry["url"].rstrip("/").rsplit("/", 1)[-1])

        species = _fetch_json_cached(
            f"{base_url}/pokemon-species/{species_id}/",
            species_dir / f"{species_id}.json",
            rate_limit_seconds=rate_limit_seconds,
        )

        # The default variety is the canonical form whose /pokemon entry has the stats.
        default_url = next(
            (v["pokemon"]["url"] for v in species["varieties"] if v.get("is_default")),
            species["varieties"][0]["pokemon"]["url"],
        )
        pokemon_id = int(default_url.rstrip("/").rsplit("/", 1)[-1])

        pokemon = _fetch_json_cached(
            f"{base_url}/pokemon/{pokemon_id}/",
            pokemon_dir / f"{pokemon_id}.json",
            rate_limit_seconds=rate_limit_seconds,
        )

        stats = {s["stat"]["name"]: s["base_stat"] for s in pokemon["stats"]}
        types = [t["type"]["name"] for t in pokemon["types"]]

        record: dict[str, Any] = {
            "species_id": species_id,
            "name": entry["name"],
            "generation": species["generation"]["name"],
            "is_legendary": bool(species["is_legendary"]),
            "is_mythical": bool(species["is_mythical"]),
            "type_1": types[0] if types else None,
            "type_2": types[1] if len(types) > 1 else None,
        }
        for api_name, col in _POKEAPI_STAT_COLUMNS.items():
            record[col] = int(stats[api_name])
        record["base_stat_total"] = sum(
            record[col] for col in _POKEAPI_STAT_COLUMNS.values()
        )
        records.append(record)

        if i % progress_every == 0 or i == total:
            print(f"  …{i}/{total} species")

    df = pd.DataFrame.from_records(records)
    df = df.sort_values("species_id").reset_index(drop=True)
    return df


def ingest_source(
    name: str,
    cfg: dict,
    save_raw: bool = True,
    js_wait_selector: str | None = None,
    row_selector: str | None = None,
    field_map: dict[str, str] | None = None,
    rate_limit_seconds: float = 1.0,
) -> pd.DataFrame:
    """Ingest a named source from config.yaml and return a DataFrame.

    Args:
        name:               Key under `sources:` in config.yaml.
        cfg:                Loaded config dict (from load_config()).
        save_raw:           If True, save the raw HTML/bytes to data/raw/.
        js_wait_selector:   Passed to fetch_html_js() if js_render is true.
        row_selector:       Required for html_scrape type.
        field_map:          Required for html_scrape type.
        rate_limit_seconds: Polite delay before fetching.
    """
    source = cfg["sources"][name]
    url: str = source["url"]
    source_type: str = source.get("type", "html_table")
    js_render: bool = source.get("js_render", False)
    table_index: int = source.get("table_index", 0)

    time.sleep(rate_limit_seconds)

    if source_type == "csv":
        dest = raw_path(cfg, f"{name}.csv")
        download_file(url, dest)
        return pd.read_csv(dest, encoding=cfg["settings"]["encoding"])

    if source_type == "json":
        dest = raw_path(cfg, f"{name}.json")
        download_file(url, dest)
        with open(dest, encoding=cfg["settings"]["encoding"]) as f:
            data = json.load(f)
        return pd.json_normalize(data)

    # HTML-based types
    html = fetch_html_js(url, wait_selector=js_wait_selector) if js_render else fetch_html(url)

    if save_raw:
        raw_path(cfg, f"{name}.html").write_text(html, encoding="utf-8")

    if source_type == "html_table":
        return parse_html_table(html, table_index=table_index)

    if source_type == "html_scrape":
        if row_selector is None or field_map is None:
            raise ValueError("html_scrape requires row_selector and field_map arguments.")
        return parse_html_scrape(html, row_selector, field_map)

    raise ValueError(f"Unknown source type '{source_type}'. Use: html_table, html_scrape, csv, json.")
