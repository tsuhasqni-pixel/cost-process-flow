"""Simple JSON-backed WIP journal (this repo's own data)."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

WIP_FILE = Path(__file__).resolve().parent.parent / "data" / "wip.json"


def _atomic_write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def load() -> list[dict]:
    if not WIP_FILE.exists():
        return []
    with WIP_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def save(entries: list[dict]) -> None:
    _atomic_write(WIP_FILE, entries)


def upsert(entry: dict) -> None:
    items = load()
    key = (entry["product_id"], entry["process"], entry["period"])
    for i, e in enumerate(items):
        if (e["product_id"], e["process"], e["period"]) == key:
            items[i] = entry
            break
    else:
        items.append(entry)
    save(items)


def delete(product_id: str, process: str, period: str) -> None:
    items = [e for e in load() if not (e["product_id"] == product_id and e["process"] == process and e["period"] == period)]
    save(items)
