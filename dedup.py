from __future__ import annotations
from typing import List
from models import NormalizedEntry
from log import log


def deduplicate(entries: list[NormalizedEntry], scope: str = "") -> list[NormalizedEntry]:
    seen: set[str] = set()
    out: list[NormalizedEntry] = []
    total = len(entries)
    for i, e in enumerate(entries, 1):
        key = e.dedup_key(scope)
        if key in seen:
            primary = e.title_candidates[0] if e.title_candidates else "?"
            log("DEDUP", i, total, primary, e.source, f"skipped (dup key={key[:12]}...)")
            continue
        seen.add(key)
        out.append(e)
    return out
