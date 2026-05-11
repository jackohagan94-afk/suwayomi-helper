# Changelog

## v2.0.0 (2026-05-11)

Major performance and matching improvements.

### Added
- **Parallel source resolution** — Phase 2 searches all sources concurrently per entry (ThreadPoolExecutor)
- **Token bucket rate limiter** — smarter rate limiting than fixed `time.sleep`, thread-safe
- **Title normalization** — strips special characters, common suffixes, boosts exact matches
- **Chapter count sanity check** — penalizes matches with wildly different chapter counts
- **Config validation on startup** — validates `lists.json` structure before running
- **Connectivity check** — warns if Suwayomi instances are unreachable or have few sources
- **Graceful shutdown** — Ctrl+C finishes current entry, prints partial results, clean exit
- **File logging** — all output written to `pipeline.log` in addition to stdout
- **`--log-file` / `--no-log-file` / `--workers` CLI flags**

### Changed
- Phase 2 resolve now uses `ThreadPoolExecutor` for parallel source queries per entry
- Matcher uses normalized titles with suffix stripping for better match rates
- Rate limiter uses token bucket algorithm (configurable via `--delay`)

### Fixed
- Unicode encoding issues on Windows console (full fix in log.py)
- Config with missing fields now fails early with clear error messages

## v1.0.0 (2026-05-11)

Full refactor of monolithic `anilist-import.py` into a modular Phase 1/2/3 pipeline.

### Added
- Three-phase architecture: Ingest -> Resolve -> Import
- Two-instance support with per-list routing (`route: manga|ecchi`)
- Genre-based routing with compound rules (Romance+NSFW -> ecchi)
- JSON persistence (`mappings.json`) for cross-run deduplication
- JSON Schema validation for `lists.json`
- MAL stack integration via DOM/JSON-LD/Next.js extraction
- `--dry-run`, `--bind-tracker`, `--anilist-token` CLI flags
- Rate-limited source searches (configurable delay)

### Fixed
- Duplicate imports on re-runs (persistent mapping store)
- Cross-source duplicates within a single run (in-memory dedup)
- Crash on AniList/MAL API failures (graceful degrade)
- Missing category creation and assignment for new lists
- Unicode encoding errors on Windows console
