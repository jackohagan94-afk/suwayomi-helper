from __future__ import annotations
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from models import NormalizedEntry, ResolvedMapping
from log import log
from matcher import best_match, score as score_titles
import suwayomi
from ratelimit import TokenBucket
import reporter


def _search_source(url: str, source_id: str, title: str,
                   candidates: list[str], threshold: float,
                   expected_chapters: int | None, bucket: TokenBucket) -> tuple[dict | None, float, str | None, float]:
    bucket.acquire()
    t0 = time.monotonic()
    try:
        r = suwayomi.search(url, source_id, title)
    except Exception:
        elapsed = time.monotonic() - t0
        return None, 0.0, None, elapsed
    elapsed = time.monotonic() - t0
    manga, s = best_match(r, candidates, threshold, expected_chapters)
    reporter.record_search(source_id, elapsed, matched=(manga is not None))
    if manga:
        return manga, s, source_id, elapsed
    return None, 0.0, None, elapsed


def resolve(entries: list[NormalizedEntry], instances: dict[str, dict],
            threshold: float = 0.85, delay: float = 1.0,
            workers: int = 2) -> list[ResolvedMapping]:
    results: list[ResolvedMapping] = []
    total = len(entries)
    bucket = TokenBucket(rate=1.0 / delay if delay > 0 else 10.0, burst=3)

    for i, entry in enumerate(entries, 1):
        t0 = time.monotonic()
        route = entry.route
        inst = instances.get(route, {})
        url = inst.get("url", "http://localhost:4567")
        sources = inst.get("sources", [])

        primary = entry.title_candidates[0] if entry.title_candidates else "?"
        src_name = entry.source

        log("P2", i, total, primary, src_name, "matching...")

        found_manga = None
        found_score = 0.0
        found_source = None
        source_ids = sources

        for title in entry.title_candidates:
            if found_manga:
                break
            pool = ThreadPoolExecutor(max_workers=workers)
            fut_map = {
                pool.submit(_search_source, url, sid, title,
                            entry.title_candidates, threshold,
                            entry.metadata.get("chapters"), bucket): sid
                for sid in source_ids
            }
            for fut in as_completed(fut_map):
                manga, s, sid, _ = fut.result()
                if manga and s > found_score:
                    found_manga = manga
                    found_score = s
                    found_source = sid
                    for f in fut_map:
                        f.cancel()
                    break
            pool.shutdown(wait=False)

        search_time = time.monotonic() - t0

        if not found_manga:
            log("P2", i, total, primary, src_name, "no match")
            reporter.record_match(entry, None, 0.0, search_time, None)
            results.append(ResolvedMapping(
                source_entry=entry,
                instance=route,
            ))
            continue

        log("P2", i, total, primary, src_name,
            f"matched '{found_manga['title']}' ({found_score:.0%})")

        if found_manga.get("inLibrary"):
            log("P2", i, total, primary, src_name, "already in library")

        reporter.record_match(entry, found_manga, found_score, search_time, found_source)

        results.append(ResolvedMapping(
            source_entry=entry,
            matched_manga=found_manga,
            confidence=found_score,
            instance=route,
        ))

    return results
