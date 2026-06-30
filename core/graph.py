"""Build a graph spec for a product flow: materials → process_1 → … → process_n.

Each node carries its variance overlay and (optionally) the WIP balance read
from the WIP journal.
"""
from __future__ import annotations

from typing import Iterable

from . import variance_overlay


def flow_for_product(product: dict, actual: dict | None, wip_entries: list[dict] | None = None) -> dict:
    cc = product.get("cost_card", {}) or {}
    labors = cc.get("labors", []) or []
    materials = cc.get("materials", []) or []

    overlay = variance_overlay.variance_overlay(product, actual) if actual else {"mode": product.get("mode", "detailed"), "per_process": {}, "overhead": {}, "total": 0}

    wip_by_process = {}
    if wip_entries:
        period = (actual or {}).get("period")
        for w in wip_entries:
            if w["product_id"] != product["id"]:
                continue
            if period and w.get("period") != period:
                continue
            wip_by_process[w["process"]] = w

    nodes = []
    # Materials node
    if materials:
        nodes.append({
            "kind": "materials", "label": "材料投入",
            "detail": [f"{m['name']}: {m.get('std_qty', 0):g} @ ¥{m.get('std_price', 0):,.0f}" for m in materials],
        })

    # Process nodes from labors
    for l in labors:
        name = l["process"]
        process_var = overlay.get("per_process", {}).get(name, {})
        wip = wip_by_process.get(name)
        nodes.append({
            "kind": "process", "label": name,
            "detail": [
                f"標準: {l.get('std_hours', 0):g}h × ¥{l.get('std_rate', 0):,.0f}",
                f"実際: {process_var.get('actual_hours', 0):g}h × ¥{process_var.get('actual_rate', 0):,.0f}" if process_var else "実績未入力",
            ],
            "rate_var": process_var.get("rate_var", 0),
            "time_var": process_var.get("time_var", 0),
            "total_var": process_var.get("total", 0),
            "wip": ({
                "beginning": wip.get("beginning", 0),
                "inputs": wip.get("inputs", 0),
                "completed": wip.get("completed", 0),
                "ending": (wip.get("beginning", 0) + wip.get("inputs", 0) - wip.get("completed", 0)),
            } if wip else None),
        })

    # Completion node
    if labors:
        nodes.append({
            "kind": "completion", "label": "完成",
            "detail": [f"完成数量: {(actual or {}).get('actual_output', '?')}"],
        })

    # OH node summary
    oh_summary = overlay.get("overhead", {}) or {}
    if oh_summary:
        nodes.append({
            "kind": "oh", "label": "製造間接費 (OH)",
            "detail": [
                f"変動OH予算差異: {oh_summary.get('voh_budget', 0):+,.0f}",
                f"変動OH能率差異: {oh_summary.get('voh_efficiency', 0):+,.0f}",
                f"固定OH予算差異: {oh_summary.get('foh_budget', 0):+,.0f}",
                f"固定OH操業度差異: {oh_summary.get('foh_volume', 0):+,.0f}",
            ],
            "total_var": oh_summary.get("total", 0),
        })

    return {
        "product_id": product["id"], "product_name": product["name"],
        "period": (actual or {}).get("period", ""),
        "mode": product.get("mode", "detailed"),
        "nodes": nodes,
        "total_variance": overlay.get("total", 0),
    }


def origin_map(data: dict, wip_entries: list[dict] | None = None) -> list[dict]:
    """Cross-product aggregation by process name: shows which processes are
    persistently unfavourable across the portfolio.
    """
    agg: dict[str, dict] = {}
    for actual in data["actuals"]:
        product = data["products_by_id"].get(actual["product_id"])
        if not product or product.get("mode") != "detailed":
            continue
        flow = flow_for_product(product, actual, wip_entries)
        for node in flow["nodes"]:
            if node["kind"] != "process":
                continue
            e = agg.setdefault(node["label"], {
                "process": node["label"], "appearances": 0,
                "rate_var": 0.0, "time_var": 0.0, "total_var": 0.0,
                "products": set(),
            })
            e["appearances"] += 1
            e["rate_var"] += node.get("rate_var", 0)
            e["time_var"] += node.get("time_var", 0)
            e["total_var"] += node.get("total_var", 0)
            e["products"].add(product["name"])
    for v in agg.values():
        v["products"] = sorted(v["products"])
    return sorted(agg.values(), key=lambda x: x["total_var"], reverse=True)
