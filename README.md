# Suwayomi-Helper

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Import manga from AniList and MyAnimeList into [Suwayomi](https://github.com/Suwayomi/Suwayomi-Server) with genre-based routing, parallel source matching, deduplication, and category assignment.

```
lists.json ──► Ingest ──► Route ──► Dedup ──► Resolve ──► Import
                  │          │         │           │            │
            AniList/MAL   genre-    remove     parallel       add to
            user lists    based    duplicates  source       library +
                          routing              search       categories
```

## Quick Start

```bash
git clone https://github.com/jackohagan94-afk/suwayomi-helper.git
cd suwayomi-helper
cp lists.example.json lists.json    # edit with your AniList users and source IDs
pip install beautifulsoup4 lxml
python3 pipeline.py
```

## Pipeline Phases

| Phase | What it does |
|---|---|
| **Ingest** | Fetches manga lists from AniList (user lists, top rankings, specific IDs) and MyAnimeList stacks |
| **Route** | Directs entries to `manga` or `ecchi` instances based on genre. `isAdult` always goes to ecchi |
| **Dedup** | In-memory SHA-256 dedup + `mappings.json` cross-run skip |
| **Resolve** | Parallel source search with fuzzy title matching, chapter count verification, early cancellation |
| **Import** | Adds to library, creates/assigns categories, optionally binds AniList tracker |

## CLI Options

| Option | Default | Description |
|---|---|---|
| `--config FILE` | `lists.json` | Config file |
| `--threshold N` | `85` | Match threshold (0–100) |
| `--delay SECS` | `1.0` | Min delay between API calls |
| `--workers N` | `3` | Parallel source searches |
| `--batch-size N` | `25` | Entries per batch |
| `--dry-run` | off | Preview only |
| `--bind-tracker` | off | Bind AniList tracker after import |
| `--anilist-token TOKEN` | — | For private AniList lists |
| `--log-file FILE` | `pipeline.log` | Log output path |

## Configuration

Copy `lists.example.json` to `lists.json`:

```json
{
  "instances": {
    "manga": { "url": "http://localhost:4567", "sources": ["SOURCE_ID"] },
    "ecchi":  { "url": "http://localhost:4568", "sources": ["SOURCE_ID"] }
  },
  "routing": {
    "default_route": "manga",
    "genres": { "manga": ["Action", ...], "ecchi": ["Ecchi", ...] }
  },
  "lists": [
    { "type": "anilist_user", "username": "your_user", "label": "My List" },
    { "type": "anilist_top", "sort": "POPULARITY_DESC", "count": 100, "label": "Top 100" }
  ]
}
```

**List types:** `anilist_user`, `anilist_top`, `anilist_ids`, `mal_stack`

## Modules

| File | Purpose |
|---|---|
| `pipeline.py` | Entry point — orchestration with batched processing and resume support |
| `phase1.py` | AniList + MAL list ingest |
| `phase2.py` | Parallel source resolution with fuzzy matching |
| `phase3.py` | Library import, category assignment, tracker binding |
| `router.py` | Genre-based routing engine |
| `matcher.py` | Fuzzy title matching with normalization and aliases |
| `suwayomi.py` | GraphQL client for Suwayomi API |
| `anilist.py` | AniList GraphQL client |
| `mal_stacks.py` | MyAnimeList stack scraper |
| `persist.py` | Thread-safe JSON persistence |
| `dedup.py` | In-memory deduplication |
| `ratelimit.py` | Token bucket rate limiter |
| `log.py` | Logging with Unicode-safe console output |
| `models.py` | Data classes |

## Data Files

| File | Purpose |
|---|---|
| `mappings.json` | Cross-run dedup store — auto-created |
| `report.json` | Per-run structured report |
| `pipeline.log` | Append-only log |

## Use Cases

```bash
# Basic import
python3 pipeline.py

# Dry run preview
python3 pipeline.py --dry-run

# Private AniList lists
python3 pipeline.py --anilist-token YOUR_TOKEN

# Bind trackers after import
python3 pipeline.py --bind-tracker

# Resume interrupted run (mappings.json skips completed)
python3 pipeline.py
```

## License

MIT
