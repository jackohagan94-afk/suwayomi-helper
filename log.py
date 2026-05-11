import sys
import os
from datetime import datetime
from typing import Any, Optional

_LOG_FILE: Optional[str] = None
_LOG_FH = None


def init_log_file(path: str = "pipeline.log") -> None:
    global _LOG_FILE, _LOG_FH
    _LOG_FILE = path
    if _LOG_FH:
        try:
            _LOG_FH.close()
        except Exception:
            pass
    try:
        _LOG_FH = open(path, "a", encoding="utf-8")
    except Exception:
        _LOG_FH = None


def close_log() -> None:
    global _LOG_FH
    if _LOG_FH:
        try:
            _LOG_FH.close()
        except Exception:
            pass
        _LOG_FH = None


def _safe(text: str) -> str:
    enc = sys.stdout.encoding or "utf-8"
    try:
        text.encode(enc)
        return text
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text.encode(enc, errors="replace").decode(enc, errors="replace")


def _write(text: str) -> None:
    print(_safe(text))
    if _LOG_FH:
        try:
            _LOG_FH.write(text + "\n")
            _LOG_FH.flush()
        except Exception:
            pass


def log(phase: str, index: int, total: int, title: str, source: str, *messages: Any) -> None:
    ts = datetime.now().strftime("%H:%M:%S")
    parts = " -> ".join(str(m) for m in messages)
    _write(f"[{ts}][{phase}][{index}/{total}] {title} ({source}) {parts}")


def summary(title: str, values: dict[str, int]) -> None:
    sep = "=" * 60
    _write(f"\n{sep}")
    _write(f" {title}")
    _write(f"{sep}")
    for k, v in values.items():
        _write(f"  {k}: {v}")
    _write("")
