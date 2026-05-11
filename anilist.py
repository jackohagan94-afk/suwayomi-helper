from __future__ import annotations
import json
import urllib.request
import urllib.error
from typing import List, Optional
from models import NormalizedEntry

ANILIST_URL = "https://graphql.anilist.co"
_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _gql(query: str, variables: dict = None, token: str = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": _USER_AGENT,
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://anilist.co",
        "Referer": "https://anilist.co/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(ANILIST_URL, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read())
    except Exception:
        return {}


_USER_LIST_QUERY = """
query ($userName: String) {
  MediaListCollection(userName: $userName, type: MANGA) {
    lists {
      name
      entries {
        status
        progress
        score(format: POINT_100)
        media {
          id
          title { romaji english native }
          format
          status
          chapters
          isAdult
          genres
        }
      }
    }
  }
}
"""

STATUS_LABELS = {
    "CURRENT": "Reading", "COMPLETED": "Completed", "PAUSED": "Paused",
    "DROPPED": "Dropped", "PLANNING": "Planning", "REPEATING": "Rereading",
}


def _make_entry(media: dict, status: str = "PLANNING", progress: int = 0, score: int = 0,
                category: str = "", source: str = "anilist") -> NormalizedEntry:
    titles = media.get("title", {})
    candidates = [t for t in (titles.get("english"), titles.get("romaji"), titles.get("native")) if t]
    return NormalizedEntry(
        title_candidates=candidates,
        external_id=str(media.get("id", "")),
        source=source,
        status=status,
        metadata={
            "category": category,
            "progress": progress,
            "score": score,
            "media_status": media.get("status", ""),
            "chapters": media.get("chapters"),
            "format": media.get("format", ""),
            "isAdult": media.get("isAdult", False),
            "genres": media.get("genres", []),
        },
    )


def fetch_user(username: str, status_filter: list[str] | None = None,
               token: str = None) -> list[NormalizedEntry]:
    data = _gql(_USER_LIST_QUERY, {"userName": username}, token)
    if "errors" in data or "data" not in data:
        return []
    lists = data["data"].get("MediaListCollection", {}).get("lists", [])
    entries: list[NormalizedEntry] = []
    for lst in lists:
        cat = lst.get("name", "")
        for entry in lst.get("entries", []):
            s = entry.get("status", "")
            if status_filter and s not in status_filter:
                continue
            media = entry.get("media", {})
            ne = _make_entry(
                media,
                status=STATUS_LABELS.get(s, s),
                progress=entry.get("progress", 0),
                score=entry.get("score", 0),
                category=cat,
            )
            entries.append(ne)
    return entries


_TOP_QUERY = """
query ($page: Int, $perPage: Int, $sort: [MediaSort]) {
  Page(page: $page, perPage: $perPage) {
    pageInfo { hasNextPage }
    media(type: MANGA, sort: $sort, format_not_in: [NOVEL]) {
      id
      title { romaji english native }
      format
      status
      chapters
      isAdult
      genres
    }
  }
}
"""


def fetch_top(count: int = 100, sort: str = "SCORE_DESC",
              status_filter: list[str] | None = None) -> list[NormalizedEntry]:
    entries: list[NormalizedEntry] = []
    page = 1
    while len(entries) < count:
        per_page = min(count - len(entries), 50)
        data = _gql(_TOP_QUERY, {"page": page, "perPage": per_page, "sort": [sort]})
        if "errors" in data or "data" not in data:
            break
        pg = data["data"].get("Page", {})
        for media in pg.get("media", []):
            ne = _make_entry(media, source="anilist_top")
            entries.append(ne)
            if len(entries) >= count:
                break
        if not pg.get("pageInfo", {}).get("hasNextPage"):
            break
        page += 1
    return entries


_IDS_QUERY = """
query ($ids: [Int]) {
  Page(perPage: 50) {
    media(type: MANGA, id_in: $ids) {
      id
      title { romaji english native }
      format
      status
      chapters
      isAdult
      genres
    }
  }
}
"""


def fetch_ids(ids: list[int]) -> list[NormalizedEntry]:
    if not ids:
        return []
    data = _gql(_IDS_QUERY, {"ids": ids})
    if "errors" in data or "data" not in data:
        return []
    entries: list[NormalizedEntry] = []
    for media in data["data"].get("Page", {}).get("media", []):
        ne = _make_entry(media, source="anilist_ids")
        entries.append(ne)
    return entries


def resolve_source_name(entry: NormalizedEntry) -> str:
    if entry.source in ("anilist", "anilist_top", "anilist_ids"):
        return "AniList"
    return entry.source
