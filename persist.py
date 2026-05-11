import json
import os
import shutil
from datetime import datetime, timezone

MAPPINGS_FILE = "mappings.json"


def _path():
    return os.environ.get("SUWAYOMI_MAPPINGS", MAPPINGS_FILE)


def _key(source: str, external_id: str) -> str:
    return f"{source}:{external_id}"


def load() -> dict:
    fp = _path()
    if not os.path.exists(fp):
        return {"version": 1, "mappings": {}}
    with open(fp) as f:
        return json.load(f)


def _save(data: dict) -> None:
    fp = _path()
    tmp = fp + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    shutil.move(tmp, fp)


def record(instance: str, source: str, external_id: str,
           suwayomi_manga_id: int, title: str, source_name: str) -> None:
    data = load()
    inst = data["mappings"].setdefault(instance, {})
    k = _key(source, external_id)
    inst[k] = {
        "suwayomi_manga_id": suwayomi_manga_id,
        "title": title,
        "source_name": source_name,
        "bound_at": datetime.now(timezone.utc).isoformat()
    }
    _save(data)


def has(instance: str, source: str, external_id: str) -> bool:
    data = load()
    inst = data["mappings"].get(instance, {})
    return _key(source, external_id) in inst


def get(instance: str, source: str, external_id: str) -> dict | None:
    data = load()
    inst = data["mappings"].get(instance, {})
    return inst.get(_key(source, external_id))
