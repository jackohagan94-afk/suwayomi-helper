from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone
from typing import Any
from collections import defaultdict

_records: list[dict] = []
_source_times: dict[str, list[float]] = defaultdict(list)
_source_matches: dict[str, int] = defaultdict(int)
_phase_timing: dict[str, float] = {}
_import_stats: dict[str, int] = defaultdict(int)
_no_match_titles: list[dict] = []


def start_phase(name: str) -> None:
    _phase_timing[name] = time.time()


def end_phase(name: str) -> None:
    if name in _phase_timing:
        _phase_timing[name] = time.time() - _phase_timing[name]


def record_search(source_id: str, elapsed: float, matched: bool) -> None:
    _source_times[source_id].append(elapsed)
    if matched:
        _source_matches[source_id] += 1


def record_match(entry, matched_manga: dict | None, confidence: float,
                 search_time: float, source_id: str | None) -> None:
    primary = entry.title_candidates[0] if entry.title_candidates else "?"
    rec = {
        "title": primary,
        "source": entry.source,
        "external_id": entry.external_id,
        "route": entry.route,
        "status": "matched" if matched_manga else "no_match",
        "confidence": round(confidence, 4),
        "matched_title": matched_manga.get("title", "") if matched_manga else "",
        "matched_id": matched_manga.get("id") if matched_manga else None,
        "via_source": source_id or "",
        "search_time_ms": round(search_time * 1000),
        "chapters": entry.metadata.get("chapters"),
        "genres": entry.metadata.get("genres", []),
    }
    _records.append(rec)
    if not matched_manga:
        _no_match_titles.append(rec)


def record_import(entry, manga_id: int | None, status: str) -> None:
    _import_stats[status] += 1
    primary = entry.title_candidates[0] if entry.title_candidates else "?"
    # Update last matching record with import status
    for rec in reversed(_records):
        if rec["title"] == primary and rec["external_id"] == entry.external_id:
            rec["import_status"] = status
            rec["suwayomi_id"] = manga_id
            break


def write_report(path: str = "report.json") -> None:
    report: dict[str, Any] = {
        "run_id": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "summary": {
            "total_entries": len(_records),
            "matched": sum(1 for r in _records if r["status"] == "matched"),
            "no_match": sum(1 for r in _records if r["status"] == "no_match"),
            "imported": _import_stats.get("imported", 0),
            "already_in_library": _import_stats.get("already_in_library", 0),
            "skipped_dup": _import_stats.get("skipped_dup", 0),
            "errors": _import_stats.get("errors", 0),
        },
        "source_performance": _build_source_stats(),
        "phase_timing": dict(_phase_timing),
        "misses": _no_match_titles[:100],  # top 100 misses
        "matches": [r for r in _records if r["status"] == "matched"],
        "all_records": _records,
    }

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    os.replace(tmp, path)


def _build_source_stats() -> dict:
    stats = {}
    for sid, times in _source_times.items():
        stats[sid] = {
            "searches": len(times),
            "matches": _source_matches.get(sid, 0),
            "avg_time_ms": round((sum(times) / len(times)) * 1000) if times else 0,
            "min_time_ms": round(min(times) * 1000) if times else 0,
            "max_time_ms": round(max(times) * 1000) if times else 0,
        }
    return stats


def reset() -> None:
    _records.clear()
    _source_times.clear()
    _source_matches.clear()
    _phase_timing.clear()
    _import_stats.clear()
    _no_match_titles.clear()
