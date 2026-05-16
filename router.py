from __future__ import annotations
from models import NormalizedEntry
from log import log


def apply_routing(entries: list[NormalizedEntry],
                  route_genres: dict[str, list[str]],
                  default_route: str = "default") -> list[NormalizedEntry]:
    if not route_genres:
        for e in entries:
            e.route = default_route
        return entries

    out: list[NormalizedEntry] = []
    total = len(entries)

    for i, entry in enumerate(entries, 1):
        genres = [g.lower() for g in entry.metadata.get("genres", [])]
        primary = entry.title_candidates[0] if entry.title_candidates else "?"

        matched_routes: set[str] = set()
        for route, genre_list in route_genres.items():
            for g in genres:
                if g in [x.lower() for x in genre_list]:
                    matched_routes.add(route)
                    break

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
