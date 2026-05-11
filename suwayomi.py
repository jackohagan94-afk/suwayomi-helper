from __future__ import annotations
import json
import urllib.request
import urllib.error


GQL_TIMEOUT = 30


def gql(url: str, query: str, variables: dict = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(
        f"{url}/api/graphql",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "suwayomi-pipeline/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=GQL_TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors="replace")[:500]
        return {"errors": [{"message": f"HTTP {e.code}: {err}"}]}
    except Exception as e:
        return {"errors": [{"message": str(e)}]}


_SEARCH_MUTATION = """
mutation ($source: LongString!, $query: String!) {
  fetchSourceManga(input: { source: $source, type: SEARCH, query: $query, page: 1 }) {
    mangas { id title inLibrary }
  }
}
"""


def search(url: str, source_id: str, query: str) -> list[dict]:
    data = gql(url, _SEARCH_MUTATION, {"source": source_id, "query": query})
    if "errors" in data:
        return []
    return data.get("data", {}).get("fetchSourceManga", {}).get("mangas", [])


_LIBRARY_MUTATION = """
mutation ($id: Int!) {
  updateManga(input: { id: $id, patch: { inLibrary: true } }) {
    manga { id title inLibrary }
  }
}
"""


def add_to_library(url: str, manga_id: int) -> dict:
    data = gql(url, _LIBRARY_MUTATION, {"id": manga_id})
    return data.get("data", {}).get("updateManga", {}).get("manga", {})


_SOURCES_QUERY = """
{ sources { nodes { id name } } }
"""


def get_sources(url: str) -> list[dict]:
    data = gql(url, _SOURCES_QUERY)
    if "errors" in data:
        return []
    return data.get("data", {}).get("sources", {}).get("nodes", [])


_CATEGORIES_QUERY = """
{ categories { nodes { id name } } }
"""


def get_categories(url: str) -> list[dict]:
    data = gql(url, _CATEGORIES_QUERY)
    if "errors" in data:
        return []
    return data.get("data", {}).get("categories", {}).get("nodes", [])


_CREATE_CATEGORY_MUTATION = """
mutation ($name: String!) {
  createCategory(input: { name: $name }) {
    category { id name }
  }
}
"""


def create_category(url: str, name: str) -> dict | None:
    data = gql(url, _CREATE_CATEGORY_MUTATION, {"name": name})
    if "errors" in data:
        return None
    return data.get("data", {}).get("createCategory", {}).get("category")


_ASSIGN_CATEGORY_MUTATION = """
mutation ($mangaId: Int!, $categoryId: Int!) {
  updateMangaCategories(input: {
    id: $mangaId,
    patch: { addToCategories: [$categoryId] }
  }) {
    manga { id title }
  }
}
"""


def assign_category(url: str, manga_id: int, category_id: int) -> bool:
    data = gql(url, _ASSIGN_CATEGORY_MUTATION, {
        "mangaId": manga_id, "categoryId": category_id,
    })
    return "errors" not in data


_BIND_TRACKER_MUTATION = """
mutation ($mangaId: Int!, $remoteId: LongString!, $trackerId: Int!) {
  bindTrack(input: { mangaId: $mangaId, remoteId: $remoteId, trackerId: $trackerId }) {
    trackRecord { id }
  }
}
"""

ANILIST_TRACKER_ID = 2


def bind_tracker(url: str, manga_id: int, remote_id: str, tracker_id: int = ANILIST_TRACKER_ID) -> bool:
    data = gql(url, _BIND_TRACKER_MUTATION, {
        "mangaId": manga_id,
        "remoteId": remote_id,
        "trackerId": tracker_id,
    })
    return "errors" not in data
