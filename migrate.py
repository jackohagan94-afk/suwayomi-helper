#!/usr/bin/env python3
"""
Suwayomi source migrator — batch migrate library manga to better sources.
Priority: Weeb Central > Comix > MangaDemon > Kagane > Atsumaru

Usage:
    python3 migrate.py [--dry-run]
    python3 migrate.py          # migrate manga library (4567)
"""

from __future__ import annotations
import json
import sys
import urllib.request
import urllib.error

URL = "http://localhost:4567"

SOURCE_PRIORITY = [
    ("Weeb Central",      "2131019126180322627"),
    ("Comix",             "7537715367149829912"),
    ("Manga Demon",       "2900023289777642714"),
    ("Kagane",            "4024736764982024684"),
    ("Atsumaru",          "2327480808438768017"),
]

TRACKER_ID = 2  # AniList


def gql(query: str, variables: dict = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{URL}/api/graphql", data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"errors": [{"message": str(e)}]}


def rank(source_id: str | None) -> int:
    if not source_id:
        return 999
    for i, (_, sid) in enumerate(SOURCE_PRIORITY):
        if sid == source_id:
            return i
    return 999


# ── Queries ───────────────────────────────────────────────────
LIBRARY_QUERY = """query($offset: Int!) {
  mangas(condition: {inLibrary: true}, offset: $offset, first: 100) {
    nodes { id title source { id name } categories { nodes { id name } } trackRecords { nodes { id trackerId remoteId } } }
  }
}"""

SEARCH = """mutation($src: LongString!, $q: String!) {
  fetchSourceManga(input: { source: $src, type: SEARCH, query: $q, page: 1 }) {
    mangas { id title inLibrary }
  }
}"""

ADD_LIB = """mutation($id: Int!) {
  updateManga(input: { id: $id, patch: { inLibrary: true } }) { manga { id title inLibrary } }
}"""

REM_LIB = """mutation($id: Int!) {
  updateManga(input: { id: $id, patch: { inLibrary: false } }) { manga { id title inLibrary } }
}"""

SET_CATS = """mutation($mid: Int!, $cids: [Int!]!) {
  updateMangaCategories(input: { id: $mid, patch: { addToCategories: $cids } }) { manga { id title } }
}"""

BIND_TRACK = """mutation($mid: Int!, $rid: LongString!, $tid: Int!) {
  bindTrack(input: { mangaId: $mid, remoteId: $rid, trackerId: $tid }) { trackRecord { id } }
}"""


def main():
    dry_run = "--dry-run" in sys.argv

    print("Suwayomi Source Migrator — manga (http://localhost:4567)")
    if dry_run:
        print("DRY RUN — no changes")
    print(f"Priority: {' > '.join(n for n, _ in SOURCE_PRIORITY)}")
    print()

    # ── Get library ──────────────────────────────────────────
    all_manga = []
    offset = 0
    while True:
        data = gql(LIBRARY_QUERY, {"offset": offset})
        if "errors" in data:
            print(f"ERROR: {data['errors']}")
            sys.exit(1)
        nodes = data.get("data", {}).get("mangas", {}).get("nodes", [])
        all_manga.extend(nodes)
        if len(nodes) < 100:
            break
        offset += 100

    print(f"Library entries: {len(all_manga)}")
    print()

    # ── Process ──────────────────────────────────────────────
    stats = {"skipped_weeb": 0, "migrated": 0, "not_found": 0, "errors": 0}

    for m in all_manga:
        mid = m["id"]
        title = m["title"]
        source = m.get("source") or {}
        src_id = source.get("id")
        src_name = source.get("name", "unknown") if source else "unknown"
        cur_rank = rank(src_id)

        # Skip Weeb Central (already best)
        if cur_rank == 0:
            stats["skipped_weeb"] += 1
            continue

        # Only try sources better than current
        targets = [(n, sid) for n, sid in SOURCE_PRIORITY if rank(sid) < cur_rank]
        if not targets:
            continue

        migrated = False
        for tgt_name, tgt_sid in targets:
            result = gql(SEARCH, {"src": tgt_sid, "q": title})
            if "errors" in result:
                continue
            mangas = result.get("data", {}).get("fetchSourceManga", {}).get("mangas", [])
            if not mangas:
                continue

            new_manga = mangas[0]
            new_id = new_manga["id"]

            print(f"  [{mid}] {title}")
            print(f"    {src_name}({src_id}) -> {tgt_name}({tgt_sid})  (id={new_id})")

            if dry_run:
                migrated = True
                break

            # Add to library
            r = gql(ADD_LIB, {"id": new_id})
            if "errors" in r:
                print(f"    FAILED add: {r['errors']}")
                stats["errors"] += 1
                continue

            # Copy categories
            cat_ids = [c["id"] for c in m.get("categories", {}).get("nodes", []) if c.get("id") is not None]
            if cat_ids:
                r = gql(SET_CATS, {"mid": new_id, "cids": cat_ids})
                ok = "errors" not in r
                print(f"    categories ({len(cat_ids)}): {'OK' if ok else 'FAIL'}")

            # Copy tracker
            for tr in m.get("trackRecords", {}).get("nodes", []):
                if tr.get("trackerId") == TRACKER_ID and tr.get("remoteId"):
                    r = gql(BIND_TRACK, {"mid": new_id, "rid": str(tr["remoteId"]), "tid": TRACKER_ID})
                    ok = "errors" not in r
                    print(f"    tracker ({tr['remoteId']}): {'OK' if ok else 'FAIL'}")

            # Remove old from library
            r = gql(REM_LIB, {"id": mid})
            if "errors" not in r:
                print(f"    removed old")

            stats["migrated"] += 1
            migrated = True
            break

        if not migrated:
            stats["not_found"] += 1

    # ── Summary ──────────────────────────────────────────────
    print()
    print("=== Summary ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    if dry_run:
        print("DRY RUN — no changes made")


if __name__ == "__main__":
    main()
