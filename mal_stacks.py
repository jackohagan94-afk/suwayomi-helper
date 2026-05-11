from __future__ import annotations
import json
import urllib.request
from bs4 import BeautifulSoup
from typing import List
from models import MalStack, MalStackEntry


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; suwayomi-pipeline/1.0)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _extract_jsonld(soup: BeautifulSoup) -> List[dict]:
    out = []
    for s in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(s.string or "{}")
        except (json.JSONDecodeError, TypeError):
            continue
        items = data.get("itemListElement", [])
        for item in items:
            name = item.get("name") or item.get("item", {}).get("name")
            identifier = item.get("identifier") or item.get("item", {}).get("@id", "")
            if name:
                out.append({"title": name.strip(), "mal_id": str(identifier)})
    return out


def _extract_next_data(soup: BeautifulSoup) -> List[dict]:
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return []
    try:
        data = json.loads(script.string)
    except (json.JSONDecodeError, TypeError):
        return []

    titles = []

    def walk(obj, path: str = ""):
        if isinstance(obj, dict):
            node_id = obj.get("@id") or obj.get("id", "")
            node_name = obj.get("name") or obj.get("title", "")
            if node_name and len(str(node_name)) > 3:
                titles.append({"title": str(node_name).strip(), "mal_id": str(node_id)})
            for v in obj.values():
                walk(v, path)
        elif isinstance(obj, list):
            for v in obj:
                walk(v, path)

    walk(data)
    return titles


def _extract_dom(soup: BeautifulSoup) -> List[dict]:
    titles = []
    seen = set()
    for tag in soup.select("h3, .title, .detail-title, td a[href*='/anime/'], td a[href*='/manga/']"):
        t = tag.get_text(strip=True)
        href = tag.get("href", "")
        mal_id = ""
        if href:
            parts = href.rstrip("/").split("/")
            if parts and parts[-1].isdigit():
                mal_id = parts[-1]
        if t and t not in seen:
            seen.add(t)
            titles.append({"title": t, "mal_id": mal_id})
    return titles


def _normalise(items: List[dict]) -> List[dict]:
    seen = set()
    out = []
    for item in items:
        t = item["title"].strip()
        if t and t not in seen:
            seen.add(t)
            out.append({"title": t, "mal_id": item.get("mal_id", "")})
    return out


def fetch_mal_stack(url: str) -> MalStack:
    html = _fetch_html(url)
    soup = BeautifulSoup(html, "lxml")

    entries = _extract_jsonld(soup)
    if not entries:
        entries = _extract_next_data(soup)
    if not entries:
        entries = _extract_dom(soup)

    entries = _normalise(entries)

    stack_name = soup.title.get_text(strip=True) if soup.title else "untitled"
    stack_name = stack_name.replace(" - MyAnimeList.net", "").strip()

    mal_entries = [
        MalStackEntry(title=e["title"], mal_id=e["mal_id"], status="")
        for e in entries
    ]

    return MalStack(stack_name=stack_name, entries=mal_entries)
