"""Load and normalise an internal-accounting JSON export."""
from __future__ import annotations

import json
from pathlib import Path


def load(source: str | Path | dict) -> dict:
    if isinstance(source, dict):
        data = source
    else:
        with Path(source).open("r", encoding="utf-8") as f:
            data = json.load(f)
    products = data.get("products") or []
    actuals = data.get("actuals") or []
    return {
        "products": products,
        "actuals": actuals,
        "cvp": data.get("cvp"),
        "products_by_id": {p["id"]: p for p in products},
    }
