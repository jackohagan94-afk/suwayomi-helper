"""
Reporter module for suwayomi-pipeline.
Tracks phase timings, search stats, match results, and import outcomes.
Writes report.json on completion.
"""

from __future__ import annotations
import json
import os
import time
from datetime import datetime, timezone

_REPORT_FILE = "report.json"

_state = {}


def reset():
    global _state
    _state = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "phases": {},
        "searches": [],
        "matches": [],
        "imports": [],
    }


def start_phase(name):
    _state["phases"][name] = {"start": time.monotonic()}


def end_phase(name):
    if name in _state["phases"] and "start" in _state["phases"][name]:
        elapsed = time.monotonic() - _state["phases"][name]["start"]
        _state["phases"][name]["elapsed"] = round(elapsed, 3)


def record_search(source_id, elapsed, matched):
    _state["searches"].append({
        "source": source_id,
        "elapsed": round(elapsed, 3),
        "matched": matched,
    })


def record_match(entry, manga, score, search_time, source_id):
    primary = entry.title_candidates[0] if entry.title_candidates else "?"
    _state["matches"].append({
        "title": primary,
        "source": entry.source,
        "matched_title": manga.get("title") if manga else None,
        "confidence": round(score, 4) if score else 0.0,
        "search_time": round(search_time, 3),
        "source_id": source_id,
    })


def record_import(entry, manga_id, status):
    primary = entry.title_candidates[0] if entry.title_candidates else "?"
    _state["imports"].append({
        "title": primary,
        "source": entry.source,
        "manga_id": manga_id,
        "status": status,
    })


def write_report():
    report = dict(_state)
    report["completed_at"] = datetime.now(timezone.utc).isoformat()
    report["summary"] = {
        "total_searches": len(_state["searches"]),
        "total_matches": len([m for m in _state["matches"] if m["confidence"] > 0]),
        "total_imports": len([i for i in _state["imports"] if i["status"] == "imported"]),
    }
    with open(_REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
