from __future__ import annotations
from typing import Optional
import difflib
import re


ROMAJI_TO_ENGLISH = {
    "20 seiki shounen": "20th century boys",
    "21 seiki shounen": "21st century boys",
    "kaijuu 8 gou": "kaiju no 8",
    "gokushufudou": "the way of the househusband",
    "kawaii dake ja nai shikimori san": "shikimoris not just a cutie",
    "sono bisque doll wa koi wo suru": "my dress up darling",
    "jojo stone ocean": "jojos bizarre adventure stone ocean",
    "jojolion": "jojos bizarre adventure jojolion",
    "jojo steel ball run": "jojos bizarre adventure steel ball run",
}

KOREAN_TO_ENGLISH = {
    "na honjaman level up": "solo leveling",
    "sinui tap": "tower of god",
    "sss geup": "sss class suicide hunter",
    "yeokdaegeum": "the strongest ever",
    "iphagyongbyeong": "terminal illness",
    "supyeongseon": "the horizon",
    "guwonhasoseo": "please save me",
    "zheng rong you xi 2": "honor game 2",
}


def _normalize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("×", "x")
    text = text.replace("\u534d", "")
    text = text.replace("\u2605", "")
    text = text.replace("-", " ")
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    for suffix in [" manga", " manga vol\\.\\d+", " vol\\.\\d+", " comic", " webtoon"]:
        text = re.sub(suffix + "$", "", text)
    return text.strip()


def _alias_normalize(text: str) -> str:
    normed = _normalize(text)
    if normed in ROMAJI_TO_ENGLISH:
        return ROMAJI_TO_ENGLISH[normed]
    if normed in KOREAN_TO_ENGLISH:
        return KOREAN_TO_ENGLISH[normed]
    return normed


def score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    a_norm = _normalize(a)
    b_norm = _normalize(b)
    ratio = difflib.SequenceMatcher(None, a_norm, b_norm).ratio()

    # Try alias of query title (romaji/korean → english)
    b_alias = _alias_normalize(b)
    if b_alias != b_norm:
        r = difflib.SequenceMatcher(None, a_norm, b_alias).ratio()
        if r > ratio:
            ratio = r
        if a_norm == b_alias:
            return min(1.0, ratio + 0.05)

    # Try alias of source title (source might be in romaji/korean)
    a_alias = _alias_normalize(a)
    if a_alias != a_norm:
        r = difflib.SequenceMatcher(None, a_alias, b_norm).ratio()
        if r > ratio:
            ratio = r
        if a_alias == b_norm:
            return min(1.0, ratio + 0.05)

    # Boost exact normalized matches
    if a_norm == b_norm:
        return min(1.0, ratio + 0.05)
    return ratio


def _chapter_penalty(manga: dict, expected_chapters: Optional[int], base_score: float) -> float:
    if expected_chapters is None:
        return base_score
    result_chapters = manga.get("chapterCount") or manga.get("chapters") or manga.get("totalChapters")
    if result_chapters is None or result_chapters == 0:
        return base_score
    diff = abs(result_chapters - expected_chapters)
    if diff > 500:
        return base_score * 0.5
    if diff > 100:
        return base_score * 0.8
    return base_score


def best_match(results: list[dict], titles: list[str],
               threshold: float = 0.85,
               expected_chapters: Optional[int] = None) -> tuple[Optional[dict], float]:
    best, best_score = None, 0.0
    for manga in results:
        manga_title = manga.get("title", "") or ""
        if not manga_title:
            continue
        if titles:
            s = max(score(manga_title, t) for t in titles)
        else:
            s = 0.0
        s = _chapter_penalty(manga, expected_chapters, s)
        if s > best_score:
            best, best_score = manga, s
    if best_score >= threshold:
        return best, best_score
    return None, best_score
