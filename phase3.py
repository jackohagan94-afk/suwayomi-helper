from __future__ import annotations
from models import ResolvedMapping
from log import log
from persist import has as has_mapping, record as save_mapping
import suwayomi
import reporter


def _resolve_category(url: str, name: str) -> int | None:
    cats = suwayomi.get_categories(url)
    for cat in cats:
        if cat["name"].lower() == name.lower():
            return cat["id"]
    created = suwayomi.create_category(url, name)
    return created["id"] if created else None


def _best_source_name(sources: list[dict], source_id: str) -> str:
    for s in sources:
        if s["id"] == source_id:
            return s["name"]
    return source_id


def import_mappings(mappings: list[ResolvedMapping], instances: dict[str, dict],
                    bind_tracker: bool = False, dry_run: bool = False,
                    sources_cache: dict[str, list[dict]] | None = None) -> dict[str, int]:
    stats = {"imported": 0, "already_in_library": 0, "no_match": 0, "skipped_dup": 0, "errors": 0}
    total = len(mappings)

    if sources_cache is None:
        sources_cache = {}

    for i, m in enumerate(mappings, 1):
        entry = m.source_entry
        route = entry.route
        inst = instances.get(route, {})
        url = inst.get("url", "http://localhost:4567")
        primary = entry.title_candidates[0] if entry.title_candidates else "?"
        src_name = entry.source

        if not m.matched_manga:
            stats["no_match"] += 1
            log("P3", i, total, primary, src_name, "no match, skipping")
            reporter.record_import(entry, None, "no_match")
            continue

        manga = m.matched_manga
        al_id = entry.external_id

        if has_mapping(route, entry.source, al_id):
            log("P3", i, total, primary, src_name,
                "already imported (mapping exists), skipping")
            stats["skipped_dup"] += 1
            reporter.record_import(entry, manga["id"], "skipped_dup")
            continue

        if manga.get("inLibrary"):
            log("P3", i, total, primary, src_name, "already in library (Suwayomi)")
            stats["already_in_library"] += 1
            reporter.record_import(entry, manga["id"], "already_in_library")
        elif dry_run:
            log("P3", i, total, primary, src_name, "[DRY RUN] would add to library")
            stats["imported"] += 1
            reporter.record_import(entry, manga["id"], "dry_run")
            continue
        else:
            result = suwayomi.add_to_library(url, manga["id"])
            if not result:
                log("P3", i, total, primary, src_name, "FAILED to add to library")
                stats["errors"] += 1
                reporter.record_import(entry, manga["id"], "failed")
                continue
            log("P3", i, total, primary, src_name, "added to library")
            stats["imported"] += 1
            reporter.record_import(entry, manga["id"], "imported")

        cat_name = entry.metadata.get("category", "")
        if cat_name and not dry_run:
            cat_id = _resolve_category(url, cat_name)
            if cat_id:
                ok = suwayomi.assign_category(url, manga["id"], cat_id)
                log("P3", i, total, primary, src_name,
                    f"{'assigned' if ok else 'FAILED'} category '{cat_name}'")

        if bind_tracker and al_id and not dry_run:
            ok = suwayomi.bind_tracker(url, manga["id"], al_id)
            log("P3", i, total, primary, src_name,
                f"{'bound' if ok else 'FAILED'} tracker (AniList #{al_id})")

        if not dry_run:
            source_name = _best_source_name(
                sources_cache.get(route, []), m.instance)
            save_mapping(route, entry.source, al_id, manga["id"],
                         manga.get("title", primary), source_name)

    return stats
