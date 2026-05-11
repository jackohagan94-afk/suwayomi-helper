# suwayomi-pipeline

Multi-source manga import pipeline for [Suwayomi](https://github.com/Suwayomi/Suwayomi-Server) with genre-based routing, parallel source matching, persistent deduplication, structured reporting, and batch source migration.

## Overview

Import manga from AniList and MyAnimeList stacks into multiple Suwayomi instances, automatically routing entries by genre (e.g., ecchi/hentai → dedicated instance), resolving the best match across multiple Suwayomi extensions in parallel, and assigning categories from the original list structure. A separate migration tool upgrades existing library entries to higher-priority sources.

## Architecture

```
lists.json ──► Phase 1: Ingest ──► Router ──► Dedup ──► Phase 2: Resolve ──► Phase 3: Import
                   │                │           │              │                  │
              AniList/MAL     genre-based    remove        parallel source     add to library
              user lists      routing        duplicates    search + fuzzy       + categories
                                                                 match          + tracker bind
```

## Tools

### `pipeline.py` — Import Pipeline

The core pipeline. Reads lists from a config file, resolves manga identities across Suwayomi extensions, and imports them into the correct instance with categories.

```
python3 pipeline.py [options]
```

| Option | Default | Description |
|---|---|---|
| `--config FILE` | `lists.json` | Config file path |
| `--threshold N` | `85` | Match similarity threshold (0–100) |
| `--delay SECS` | `1.0` | Min delay between source API calls |
| `--bind-tracker` | off | Bind AniList tracker record after import |
| `--dry-run` | off | Preview only, no mutations |
| `--anilist-token TOKEN` | — | AniList API token for private lists |
| `--log-file FILE` | `pipeline.log` | Write logs to file |
| `--no-log-file` | off | Disable file logging |
| `--workers N` | `3` | Parallel source searches per entry |
| `--batch-size N` | `25` | Entries per batch before checkpoint |
| `--version` | — | Show version and exit |

#### Pipeline Phases

**Phase 1 — Ingest:** Fetches manga lists from configured sources:
- `anilist_user` — AniList user's manga list (optionally filtered by status)
- `anilist_top` — AniList top/popular rankings (paginated)
- `anilist_ids` — Specific AniList IDs
- `mal_stack` — MyAnimeList stack pages (extracts titles via JSON-LD, Next.js data, or DOM)

**Genre Routing:** Each entry is routed to `manga` or `ecchi` based on genres:
- Direct genre matching against per-route genre lists
- Compound rules: Romance alone → manga, Romance + NSFW → ecchi
- Entries flagged `isAdult` always route to ecchi
- NSFW entries are never dual-routed to manga

**Dedup:** Entries with the same `(source, external_id, route)` are deduplicated in-memory. Cross-run dedup uses `mappings.json`.

**Phase 2 — Resolve:** For each entry, searches all configured Suwayomi sources in parallel using ThreadPoolExecutor. Uses fuzzy title matching with:
- Title normalization (lowercase, special character cleanup, suffix stripping)
- Romaji→English and Korean→English title aliases
- Bidirectional alias matching (both query and result titles)
- Chapter count sanity penalty (wildly mismatched counts reduce score)
- Early cancellation on first match above threshold

**Phase 3 — Import:** For each resolved match:
1. Adds manga to library (skips if already present)
2. Creates category if needed and assigns it
3. Optionally binds AniList tracker record (requires logged-in tracker in Suwayomi)
4. Records mapping in `mappings.json` for cross-run dedup

**Batch Processing:** Entries are processed in configurable batches. After each batch:
- Report is written to `report.json`
- Health check pings both Suwayomi instances
- Graceful shutdown on SIGINT (finishes current entry, saves partial results)

### `migrate.py` — Source Migration

Upgrades existing library entries to higher-quality extensions. Migrates the Suwayomi manga library (port 4567) through a priority chain.

```
python3 migrate.py [--dry-run]
```

**Priority order:** Weeb Central > Comix > Manga Demon > Kagane > Atsumaru

For each library entry not already on Weeb Central:
1. Searches each better source in priority order
2. On first match: adds to library, copies categories, copies AniList tracker, removes old from library
3. Falls through to next source if not found

### Helper scripts

- `migrate_one.py` — Migrate a single manga by ID (used for testing)
- `fix_bleach.py` — Verify/clean up after a test migration

## Configuration

### `lists.json`

```json
{
  "instances": {
    "manga": {
      "url": "http://localhost:4567",
      "sources": ["<source_id>", ...]
    },
    "ecchi": {
      "url": "http://localhost:4568",
      "sources": ["<source_id>", ...]
    }
  },
  "routing": {
    "default_route": "manga",
    "genres": {
      "manga": ["Action", "Adventure", ...],
      "ecchi": ["Ecchi", "Hentai", "Yaoi", ...]
    }
  },
  "lists": [
    {
      "type": "anilist_user",
      "username": "username",
      "label": "My List",
      "category": "Reading",
      "status": ["CURRENT", "COMPLETED"]
    },
    {
      "type": "anilist_top",
      "sort": "POPULARITY_DESC",
      "count": 100,
      "label": "Top Popular",
      "category": "Popular"
    },
    {
      "type": "anilist_ids",
      "ids": [12345, 67890],
      "label": "Custom",
      "category": "Custom"
    },
    {
      "type": "mal_stack",
      "url": "https://myanimelist.net/stacks/...",
      "label": "MAL Stack",
      "category": "Planning"
    }
  ]
}
```

#### List types

| Type | Fields | Description |
|---|---|---|
| `anilist_user` | `username`, `status` (optional filter), `token` (optional) | Fetches a user's manga list via AniList API |
| `anilist_top` | `sort` (SCORE_DESC/POPULARITY_DESC/etc), `count` | Top manga rankings, paginated |
| `anilist_ids` | `ids` (array of ints) | Specific manga by AniList ID |
| `mal_stack` | `url` (MAL stack page) | Extracts titles from a MyAnimeList stack page |

**Where to find source IDs**

You can use the Suwayomi REST API to list installed sources:
```
curl http://localhost:4567/api/v1/extension/list
```
Or the GraphQL endpoint:
```
{ sources { nodes { id name } } }
```

### `lists.schema.json`

JSON Schema for `lists.json` validation. Used by the pipeline on startup.

## Data Files

| File | Purpose |
|---|---|
| `mappings.json` | Cross-run deduplication store. Maps `(route, source, external_id)` → Suwayomi manga ID. Auto-created. |
| `report.json` | Structured per-run report with match details, source performance stats, misses, and phase timing. Written after each batch. |
| `pipeline.log` | Append-only log of all pipeline output. |

## Use Cases

### 1. Initial import from AniList

```bash
python3 pipeline.py --config lists.json
```

Imports all lists from `lists.json`, routing by genre, resolving against configured Suwayomi sources, and adding to library with categories.

### 2. Import private AniList lists

```bash
python3 pipeline.py --anilist-token YOUR_TOKEN
```

Some AniList users have private lists. Pass a personal access token (generate at AniList settings → API) to fetch them.

### 3. Preview without importing

```bash
python3 pipeline.py --dry-run
```

Runs through matching but skips all mutations. Shows what would be imported and where.

### 4. Bind AniList trackers

```bash
python3 pipeline.py --bind-tracker
```

After import, binds the AniList tracker record in Suwayomi for each manga. Requires AniList to be logged in via the Suwayomi web UI (Settings → Trackers → AniList → Login).

### 5. Resume interrupted import

Re-running the pipeline automatically skips entries already recorded in `mappings.json`:

```bash
python3 pipeline.py
```

### 6. Batch source migration

```bash
# Preview migration
python3 migrate.py --dry-run

# Run migration
python3 migrate.py
```

Upgrades all library entries to the best available source by searching the priority chain. Copies categories and removes old entries.

### 7. Migrate a single entry

```bash
python3 migrate_one.py <manga_id>
```

Test migration for a specific library entry by ID. Verifies the full workflow.

### 8. Two-instance setup

Run two Suwayomi instances (manga on :4567, ecchi on :4568). Configure sources separately per instance — use SFW extensions on manga and NSFW-capable extensions on ecchi. Genre routing ensures content reaches the correct instance.

## Module Reference

### `pipeline.py`
Entry point. Orchestrates all phases with batched processing, resume support, health checks, and graceful shutdown.

### `phase1.py`
Ingest module. Calls `anilist.py` for AniList sources and `mal_stacks.py` for MAL stacks. Each entry is a `NormalizedEntry` with title candidates, metadata, and routing info.

### `phase2.py`
Resolution engine. Uses `ThreadPoolExecutor` to search all sources for an entry in parallel. Calls `matcher.py` to score results and picks the best match above threshold. Implements early cancellation — once a match is found, remaining searches are cancelled.

### `phase3.py`
Import executor. Adds matched manga to the Suwayomi library, creates and assigns categories, optionally binds trackers, and persists mappings.

### `router.py`
Genre-based routing engine. Implements direct genre matching and compound rules (e.g., Romance + NSFW → ecchi). Enforces ecchi-exclusive routing — if ecchi is matched, manga is discarded.

### `matcher.py`
Fuzzy title matcher. Normalizes titles (× → x, special characters, suffix stripping), applies romaji→English/Korean→English aliases, scores with `difflib.SequenceMatcher`, and applies chapter count penalties.

### `suwayomi.py`
GraphQL client for Suwayomi API. Wraps all mutations and queries: search source, add to library, manage categories, list sources, bind trackers.

### `reporter.py`
Structured data collector. Records every match attempt, search timing per source, import status. Writes `report.json` with full details and per-source performance stats.

### `persist.py`
JSON persistence for `mappings.json`. Thread-safe write with atomic file replacement (temp file + rename). Used for cross-run dedup and resume.

### `dedup.py`
In-memory deduplication. Uses SHA-256 of `(source:external_id:route)` as dedup key. Removes duplicate entries within a single run.

### `ratelimit.py`
Thread-safe token bucket rate limiter. Controls API call frequency to avoid overwhelming Suwayomi sources.

### `log.py`
Logging utility. Timestamps all messages, writes to console and optional log file. Handles Unicode encoding for Windows console safely.

### `anilist.py`
AniList GraphQL client. Fetches user lists (with optional auth token), top rankings, and specific IDs. Builds `NormalizedEntry` objects with title candidates, chapters, genres, and adult flag.

### `mal_stacks.py`
MyAnimeList stack scraper. Extracts title lists from MAL stack pages using multiple extraction strategies: JSON-LD, Next.js data, and DOM parsing. Falls through strategies if one returns empty.

### `models.py`
Data classes: `NormalizedEntry` (import target), `ResolvedMapping` (match result), `MalStackEntry`/`MalStack` (MAL stack data). Includes `dedup_key()` for cross-run identity.

### `migrate.py`
Batch source migration. Standalone script (not a module). Processes all library entries in priority order, migrates to better sources, copies categories, and removes old entries.

## Dependencies

- Python 3.10+
- `beautifulsoup4` (for MAL stack parsing)
- `lxml` (for MAL stack parsing)

Install:
```bash
pip install beautifulsoup4 lxml
```
