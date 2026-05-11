from __future__ import annotations
from typing import List, Optional
from models import NormalizedEntry
from log import log
import anilist
import mal_stacks as mal


def _convert_mal(stack_entry, stack_name: str, route: str) -> NormalizedEntry:
    return NormalizedEntry(
        title_candidates=[stack_entry.title],
        external_id=stack_entry.mal_id,
        source="mal_stack",
        status=stack_entry.status,
        route=route,
        metadata={"stack_name": stack_name},
    )


def ingest(config: dict, token: str | None = None) -> list[NormalizedEntry]:
    all_entries: list[NormalizedEntry] = []
    lists = config.get("lists", [])

    for li, list_cfg in enumerate(lists, 1):
        ltype = list_cfg.get("type", "")
        route = list_cfg.get("route", "manga")
        category = list_cfg.get("category", "")
        label = list_cfg.get("label") or list_cfg.get("username") or ltype

        entries: list[NormalizedEntry] = []

        try:
            if ltype == "anilist_user":
                username = list_cfg["username"]
                status_filter = [s.upper() for s in list_cfg.get("status", [])] or None
                tk = list_cfg.get("token", token)
                entries = anilist.fetch_user(username, status_filter, tk)
                for e in entries:
                    e.metadata["username"] = username
                log("P1", li, len(lists), f"@{username}", "AniList",
                    f"fetched {len(entries)} entries")

            elif ltype == "anilist_top":
                count = list_cfg.get("count", 100)
                sort = list_cfg.get("sort", "SCORE_DESC")
                entries = anilist.fetch_top(count, sort)
                log("P1", li, len(lists), f"top {count}", "AniList",
                    f"fetched {len(entries)} entries")

            elif ltype == "anilist_ids":
                ids = list_cfg["ids"]
                entries = anilist.fetch_ids(ids)
                log("P1", li, len(lists), f"{len(ids)} IDs", "AniList",
                    f"fetched {len(entries)} entries")

            elif ltype == "mal_stack":
                url = list_cfg["url"]
                stack = mal.fetch_mal_stack(url)
                entries = [_convert_mal(e, stack.stack_name, route) for e in stack.entries]
                log("P1", li, len(lists), stack.stack_name, "MAL",
                    f"fetched {len(entries)} entries")

            else:
                log("P1", li, len(lists), label, "?", f"unknown type '{ltype}', skipping")
                continue

        except Exception as e:
            log("P1", li, len(lists), label, "?", f"FETCH FAILED: {e}")
            continue

        for e in entries:
            e.route = route
            if category and not e.metadata.get("category"):
                e.metadata["category"] = category

        all_entries.extend(entries)

    return all_entries
