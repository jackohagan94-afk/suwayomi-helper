#!/usr/bin/env python3
"""
suwayomi-pipeline  v2.0.0
Multi-source manga import pipeline for Suwayomi.

Usage:
    python3 pipeline.py [options]

Options:
    --config FILE           lists.json path (default: lists.json)
    --threshold N           match similarity 0-100 (default: 85)
    --delay SECONDS         pause between source searches (default: 0.5)
    --bind-tracker          bind AniList/MAL tracker records
    --dry-run               preview only, no mutations
    --anilist-token TOKEN   AniList API token for private lists
    --log-file FILE         write logs to file (default: pipeline.log)
    --no-log-file           disable file logging
    --workers N             parallel source searches per entry (default: 2)
    --batch-size N          entries per batch before checkpoint (default: 100)
"""

from __future__ import annotations
import json
import sys
import os
import signal
import argparse
from log import log, summary, init_log_file, close_log
import phase1
import phase2
import phase3
import dedup
import router as router_mod
import suwayomi
import reporter
import persist

VERSION = "2.0.0"

DEFAULT_SOURCES = [
    "1024627298672457456",
    "2131019126180322627",
    "734865402529567092",
    "1201694572804778862",
]

DEFAULT_INSTANCES = {
    "manga": {"url": "http://localhost:4567", "sources": DEFAULT_SOURCES},
    "ecchi": {"url": "http://localhost:4568", "sources": DEFAULT_SOURCES},
}

# ── Graceful shutdown ────────────────────────────────────────
_shutdown = False


def _handle_sigint(sig, frame):
    global _shutdown
    if _shutdown:
        sys.exit(1)
    _shutdown = True
    log("SYS", 0, 0, "Pipeline", "signal", "Ctrl+C received, finishing current entry...")


signal.signal(signal.SIGINT, _handle_sigint)


def _check_shutdown():
    if _shutdown:
        log("SYS", 0, 0, "Pipeline", "abort", "shutting down gracefully")
        close_log()
        sys.exit(0)


# ── Config ───────────────────────────────────────────────────
def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def _ensure_instances(config: dict) -> dict:
    if "instances" in config:
        return config["instances"]
    sources = config.get("sources", DEFAULT_SOURCES)
    return {
        "manga": {"url": "http://localhost:4567", "sources": list(sources)},
        "ecchi": {"url": "http://localhost:4568", "sources": list(sources)},
    }


def _validate_config(config: dict) -> list[str]:
    errors = []
    if "lists" not in config or not config["lists"]:
        errors.append("no lists defined in config")
    instances = _ensure_instances(config)
    for name, inst in instances.items():
        if "url" not in inst:
            errors.append(f"instance '{name}' missing url")
        if "sources" not in inst or not inst["sources"]:
            errors.append(f"instance '{name}' has no sources")
    for li, lst in enumerate(config.get("lists", [])):
        ltype = lst.get("type", "")
        if not ltype:
            errors.append(f"list #{li + 1} missing type")
        if ltype == "anilist_user" and "username" not in lst:
            errors.append(f"list #{li + 1} (anilist_user) missing username")
        if ltype == "anilist_ids" and "ids" not in lst:
            errors.append(f"list #{li + 1} (anilist_ids) missing ids")
        if ltype == "mal_stack" and "url" not in lst:
            errors.append(f"list #{li + 1} (mal_stack) missing url")
    return errors


def _check_connectivity(instances: dict) -> list[str]:
    warnings = []
    for name, inst in instances.items():
        url = inst.get("url", "")
        try:
            sources = suwayomi.get_sources(url)
            if len(sources) <= 1:  # only local source
                warnings.append(f"instance '{name}' ({url}) has only {len(sources)} source(s)")
        except Exception as e:
            warnings.append(f"instance '{name}' ({url}) unreachable: {e}")
    return warnings


# ── Resume helpers ────────────────────────────────────────────
def _filter_mapped(entries: list, existing: dict) -> list:
    mapped = existing.get("mappings", {})
    out = []
    for e in entries:
        inst = mapped.get(e.route, {})
        key = f"{e.source}:{e.external_id}"
        if key not in inst:
            out.append(e)
    return out


def _check_health(instances: dict) -> bool:
    for name, inst in instances.items():
        try:
            suwayomi.get_sources(inst.get("url", ""))
        except Exception:
            log("SYS", 0, 0, "Health", "warn", f"{name} unreachable")
            return False
    return True


# ── Main ─────────────────────────────────────────────────────
def main():
    global _shutdown

    parser = argparse.ArgumentParser(description="Suwayomi multi-source import pipeline")
    parser.add_argument("--config", default="lists.json")
    parser.add_argument("--threshold", type=int, default=85)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--bind-tracker", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--anilist-token")
    parser.add_argument("--log-file", default="pipeline.log")
    parser.add_argument("--no-log-file", action="store_true")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--version", action="version", version=f"suwayomi-pipeline v{VERSION}")
    args = parser.parse_args()

    threshold = args.threshold / 100.0

    if not args.no_log_file:
        init_log_file(args.log_file)

    # Load config
    try:
        config = load_config(args.config)
    except FileNotFoundError:
        print(f"ERROR: config not found: {args.config}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON: {e}")
        sys.exit(1)

    instances = _ensure_instances(config)
    lists = config.get("lists", [])

    # Validate
    config_errors = _validate_config(config)
    if config_errors:
        for e in config_errors:
            log("CFG", 0, 0, "Config", "error", e)
        sys.exit(1)
    log("CFG", 0, 0, "Config", "ok", f"loaded {args.config}")
    reporter.reset()

    # Connectivity check (warning only)
    conn_warnings = _check_connectivity(instances)
    for w in conn_warnings:
        log("CFG", 0, 0, "Connectivity", "warn", w)

    if not lists:
        log("CFG", 0, 0, "Config", "error", "no lists defined")
        sys.exit(1)

    # Resolve source names
    source_names: dict[str, list[dict]] = {}
    for name, inst in instances.items():
        try:
            source_names[name] = suwayomi.get_sources(inst.get("url", "http://localhost:4567"))
        except Exception:
            source_names[name] = []
    _check_shutdown()

    log("SYS", 0, 0, "Pipeline", "start",
        f"v{VERSION}  lists={len(lists)}  instances={list(instances.keys())}  "
        f"threshold={threshold:.0%}  bind={args.bind_tracker}  dry={args.dry_run}")

    reporter.start_phase("phase1_ingest")

    # ── Phase 1: Ingest ─────────────────────────────────────
    raw = phase1.ingest(config, token=args.anilist_token)
    reporter.end_phase("phase1_ingest")
    log("SYS", 0, 0, "Phase 1", "done", f"{len(raw)} raw entries")
    _check_shutdown()

    # ── Genre Routing ───────────────────────────────────────
    route_cfg = config.get("routing", {})
    default_route = route_cfg.get("default_route", "manga")
    genre_rules = route_cfg.get("genres", {})
    raw = router_mod.apply_routing(raw, genre_rules, default_route)
    log("SYS", 0, 0, "Routing", "done", f"{len(raw)} routed entries")
    _check_shutdown()

    # ── Dedup ───────────────────────────────────────────────
    raw = dedup.deduplicate(raw)
    log("SYS", 0, 0, "Dedup", "done", f"{len(raw)} unique entries")
    _check_shutdown()

    # ── Resume: skip already-imported ───────────────────────
    existing = persist.load()
    if existing.get("mappings"):
        before = len(raw)
        raw = _filter_mapped(raw, existing)
        skipped = before - len(raw)
        if skipped:
            log("SYS", 0, 0, "Resume", "skip", f"{skipped} already imported")
    _check_shutdown()

    # ── Batch processing ────────────────────────────────────
    batch_size = args.batch_size
    total = len(raw)
    agg = {"imported": 0, "already_in_library": 0, "no_match": 0, "skipped_dup": 0, "errors": 0}

    for batch_start in range(0, total, batch_size):
        batch = raw[batch_start:batch_start + batch_size]
        batch_label = f"{batch_start + 1}-{min(batch_start + batch_size, total)}"

        reporter.start_phase(f"phase2_b{batch_start}")
        resolved = phase2.resolve(batch, instances, threshold, args.delay, workers=args.workers)
        reporter.end_phase(f"phase2_b{batch_start}")

        reporter.start_phase(f"phase3_b{batch_start}")
        stats = phase3.import_mappings(
            resolved, instances,
            bind_tracker=args.bind_tracker,
            dry_run=args.dry_run,
            sources_cache=source_names,
        )
        reporter.end_phase(f"phase3_b{batch_start}")

        for k in agg:
            agg[k] += stats.get(k, 0)

        pct = (batch_start + len(batch)) / total * 100
        log("SYS", 0, 0, "Batch", "done",
            f"[{batch_label}/{total}] imported={agg['imported']}  "
            f"already={agg['already_in_library']}  miss={agg['no_match']}  "
            f"err={agg['errors']}  ({pct:.0f}%)")

        reporter.write_report()
        _check_shutdown()

        if not _check_health(instances):
            log("SYS", 0, 0, "Health", "wait", "instances down, pausing 30s...")
            __import__("time").sleep(30)
            if not _check_health(instances):
                log("SYS", 0, 0, "Health", "abort", "instances still down, stopping")
                break

    # ── Final ───────────────────────────────────────────────
    reporter.write_report()
    summary("Summary", agg)
    log("SYS", 0, 0, "Pipeline", "done", f"processed {total} entries")
    close_log()


if __name__ == "__main__":
    main()
