from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional
import hashlib


@dataclass
class NormalizedEntry:
    title_candidates: List[str] = field(default_factory=list)
    external_id: str = ""
    source: str = ""
    status: str = ""
    route: str = "manga"
    metadata: dict = field(default_factory=dict)

    @staticmethod
    def _normalize_source(source: str) -> str:
        source = source.lower().strip()
        # Normalize anilist variants to share dedup namespace
        for prefix in ("anilist_top", "anilist_ids", "anilist"):
            if source.startswith(prefix):
                return "anilist"
        return source

    def dedup_key(self, scope: str = "") -> str:
        if self.external_id and self.source:
            ns = self._normalize_source(self.source)
            raw = f"{scope}{ns}:{self.external_id}:{self.route}"
        else:
            raw = min((t for t in self.title_candidates if t), key=len, default="").lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()


@dataclass
class ResolvedMapping:
    source_entry: NormalizedEntry
    matched_manga: Optional[dict] = None
    confidence: float = 0.0
    instance: str = "manga"


@dataclass
class MalStackEntry:
    title: str = ""
    mal_id: str = ""
    status: str = ""


@dataclass
class MalStack:
    stack_name: str = ""
    entries: List[MalStackEntry] = field(default_factory=list)
