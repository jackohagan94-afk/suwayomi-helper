from __future__ import annotations
from typing import List
from models import NormalizedEntry
from log import log

_NSFW_GENRES = {"ecchi", "hentai", "adult", "yaoi", "yuri", "smut", "gender bender"}
_COMPOUND_RULES = [
    # Romance alone -> manga; Romance + any NSFW genre -> ecchi
    ("Romance", _NSFW_GENRES, "ecchi"),
]


def apply_routing(entries: list[NormalizedEntry],
                  route_genres: dict[str, list[str]],
                  default_route: str = "manga") -> list[NormalizedEntry]:
    out: list[NormalizedEntry] = []
    total = len(entries)

    for i, entry in enumerate(entries, 1):
        genres = [g.lower() for g in entry.metadata.get("genres", [])]
        is_adult = entry.metadata.get("isAdult", False)
        primary = entry.title_candidates[0] if entry.title_candidates else "?"

        matched_routes: set[str] = set()

        # Direct genre matching
        for route, genre_list in route_genres.items():
            for g in genres:
                if g in [x.lower() for x in genre_list]:
                    matched_routes.add(route)
                    break

        # Compound rules: romance + nsfw -> ecchi
        genre_set = set(genres)
        for trigger_genre, required_set, target_route in _COMPOUND_RULES:
            if trigger_genre.lower() in genre_set and genre_set & required_set:
                matched_routes.add(target_route)

        # NSFW override: if ecchi route is matched at all, discard manga
        if "ecchi" in matched_routes or is_adult:
            matched_routes.discard("manga")
            matched_routes.add("ecchi")

        if not matched_routes:
            matched_routes.add(default_route)

        for route in sorted(matched_routes):
            copy = NormalizedEntry(
                title_candidates=list(entry.title_candidates),
                external_id=entry.external_id,
                source=entry.source,
                status=entry.status,
                route=route,
                metadata=dict(entry.metadata),
            )
            out.append(copy)

        genre_str = ", ".join(entry.metadata.get("genres", [])[:5])
        log("ROUTE", i, total, primary, entry.source,
            f"genres=[{genre_str}]  -> {', '.join(matched_routes)}")

    return out
