"""Tests for suwayomi-helper pipeline."""

from __future__ import annotations
import pytest
import json
import os
import tempfile
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from models import NormalizedEntry, ResolvedMapping
from matcher import score, best_match, _normalize
from dedup import deduplicate
from router import apply_routing
import persist


# ── Models ───────────────────────────────────────────────────

class TestNormalizedEntry:
    def test_dedup_key_with_external_id(self):
        e = NormalizedEntry(
            title_candidates=["One Piece"],
            external_id="12345",
            source="anilist",
            route="default",
        )
        key = e.dedup_key()
        assert len(key) == 64  # SHA-256 hex
        assert isinstance(key, str)

    def test_dedup_key_normalizes_source_prefixes(self):
        e1 = NormalizedEntry(external_id="1", source="anilist_top", route="default")
        e2 = NormalizedEntry(external_id="1", source="anilist", route="default")
        # anilist_top should normalize to "anilist" so keys match
        assert e1.dedup_key() == e2.dedup_key()

    def test_dedup_key_differs_by_route(self):
        e1 = NormalizedEntry(external_id="1", source="anilist", route="manga")
        e2 = NormalizedEntry(external_id="1", source="anilist", route="ecchi")
        assert e1.dedup_key() != e2.dedup_key()


# ── Matcher ──────────────────────────────────────────────────

class TestScore:
    def test_exact_match(self):
        assert score("One Piece", "One Piece") >= 0.9

    def test_empty_strings(self):
        assert score("", "One Piece") == 0.0
        assert score("One Piece", "") == 0.0

    def test_partial_match(self):
        s = score("One Piece", "One Piece Manga")
        assert s > 0.5

    def test_romaji_alias(self):
        s = score("Kaijuu 8-gou", "Kaiju No. 8")
        assert s > 0.5

    def test_no_match(self):
        s = score("One Piece", "Naruto")
        assert s < 0.5

    def test_normalize_strips_suffixes(self):
        a = _normalize("One Piece Manga")
        b = _normalize("One Piece")
        assert a == b

    def test_normalize_special_chars(self):
        n = _normalize("One Piece!")
        assert n == "one piece"


class TestBestMatch:
    def test_best_match_found(self):
        results = [
            {"title": "One Piece", "chapters": 1000},
            {"title": "Naruto", "chapters": 700},
        ]
        match, s = best_match(results, ["One Piece"], threshold=0.8)
        assert match is not None
        assert match["title"] == "One Piece"

    def test_best_match_not_found(self):
        results = [{"title": "Naruto"}]
        match, s = best_match(results, ["One Piece"], threshold=0.9)
        assert match is None

    def test_chapter_penalty(self):
        results = [{"title": "One Piece", "chapterCount": 10}]
        match, s = best_match(results, ["One Piece"], threshold=0.0, expected_chapters=1000)
        assert match is not None
        # Chapter count penalty should reduce score
        assert s < 0.9


# ── Dedup ────────────────────────────────────────────────────

class TestDedup:
    def test_removes_duplicates(self):
        entries = [
            NormalizedEntry(title_candidates=["A"], external_id="1", source="anilist", route="default"),
            NormalizedEntry(title_candidates=["A"], external_id="1", source="anilist", route="default"),
            NormalizedEntry(title_candidates=["B"], external_id="2", source="anilist", route="default"),
        ]
        result = deduplicate(entries)
        assert len(result) == 2

    def test_preserves_unique(self):
        entries = [
            NormalizedEntry(title_candidates=["A"], external_id="1", source="anilist", route="default"),
            NormalizedEntry(title_candidates=["B"], external_id="2", source="anilist", route="default"),
        ]
        result = deduplicate(entries)
        assert len(result) == 2


# ── Router ──────────────────────────────────────────────────

class TestRouter:
    def test_pass_through_no_genres(self):
        entries = [
            NormalizedEntry(title_candidates=["A"], route="default"),
            NormalizedEntry(title_candidates=["B"], route="default"),
        ]
        result = apply_routing(entries, {}, "default")
        assert len(result) == 2
        assert all(e.route == "default" for e in result)

    def test_genre_routing(self):
        entries = [
            NormalizedEntry(
                title_candidates=["Action Manga"],
                metadata={"genres": ["Action", "Adventure"]},
            ),
        ]
        genres = {"manga": ["Action", "Adventure"]}
        result = apply_routing(entries, genres, "default")
        assert len(result) == 1
        assert result[0].route == "manga"

    def test_multiple_genre_matches(self):
        entries = [
            NormalizedEntry(
                title_candidates=["Action Romance"],
                metadata={"genres": ["Action", "Romance"]},
            ),
        ]
        genres = {"manga": ["Action"], "romance": ["Romance"]}
        result = apply_routing(entries, genres, "default")
        assert len(result) == 2


# ── Persist ──────────────────────────────────────────────────

class TestPersist:
    @pytest.fixture
    def tmp_mappings(self):
        old = os.environ.get("SUWAYOMI_MAPPINGS")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            fname = f.name
            json.dump({"version": 1, "mappings": {}}, f)
        os.environ["SUWAYOMI_MAPPINGS"] = fname
        yield fname
        os.unlink(fname)
        if old:
            os.environ["SUWAYOMI_MAPPINGS"] = old
        else:
            del os.environ["SUWAYOMI_MAPPINGS"]

    def test_record_and_has(self, tmp_mappings):
        persist.record("default", "anilist", "123", 456, "One Piece", "MangaDex")
        assert persist.has("default", "anilist", "123") is True
        assert persist.has("default", "anilist", "999") is False

    def test_get(self, tmp_mappings):
        persist.record("default", "anilist", "123", 456, "One Piece", "MangaDex")
        result = persist.get("default", "anilist", "123")
        assert result is not None
        assert result["suwayomi_manga_id"] == 456
