"""Variance calculation vendored from internal-accounting/core/variance.py.

Produces per-process variance dicts that the SVG layer overlays on each
process node.
"""
from __future__ import annotations


def _per_unit(per_unit: float, std_output: float, actual_output: float) -> float:
    if std_output <= 0:
        return 0.0
    return per_unit / std_output * actual_output


def _by_process_detailed(product: dict, actual: dict) -> dict:
    cc = product.get("cost_card", {}) or {}
    so = float(product.get("std_output", 1))
    out = float(actual.get("actual_output", 1))
    std_labs = {l["process"]: l for l in cc.get("labors", [])}
    act_labs = {l["process"]: l for l in actual.get("labors", [])}
    per_process: dict[str, dict] = {}
    total_act_hours = 0.0
    total_std_hours = 0.0
    for name in dict.fromkeys(list(std_labs) + list(act_labs)):
        s = std_labs.get(name, {"std_rate": 0, "std_hours": 0})
        a = act_labs.get(name, {"actual_rate": 0, "actual_hours": 0})
        sh = _per_unit(s["std_hours"], so, out)
        rate_var = (a["actual_rate"] - s["std_rate"]) * a["actual_hours"]
        time_var = (a["actual_hours"] - sh) * s["std_rate"]
        per_process[name] = {
            "process": name,
            "std_rate": s["std_rate"],
            "std_hours": s["std_hours"],
            "actual_rate": a["actual_rate"],
            "actual_hours": a["actual_hours"],
            "rate_var": rate_var,
            "time_var": time_var,
            "total": rate_var + time_var,
        }
        total_act_hours += a["actual_hours"]
        total_std_hours += sh

    oh = cc.get("overhead", {}) or {}
    aoh = actual.get("overhead", {}) or {}
    voh_budget = (aoh.get("actual_variable", 0)) - (oh.get("var_rate", 0)) * total_act_hours
    voh_eff = (oh.get("var_rate", 0)) * (total_act_hours - total_std_hours)
    foh_budget = (aoh.get("actual_fixed", 0)) - (oh.get("fixed_budget", 0))
    sfr = (oh.get("fixed_budget", 0) / oh["normal_hours"]) if oh.get("normal_hours") else 0
    foh_vol = (oh.get("fixed_budget", 0)) - sfr * total_std_hours
    overhead_summary = {
        "voh_budget": voh_budget,
        "voh_efficiency": voh_eff,
        "foh_budget": foh_budget,
        "foh_volume": foh_vol,
        "total": voh_budget + voh_eff + foh_budget + foh_vol,
    }
    return {"per_process": per_process, "overhead": overhead_summary}


def variance_overlay(product: dict, actual: dict) -> dict:
    if product.get("mode") == "simple":
        sb = ((product.get("cost_card") or {}).get("simple_budget") or {})
        sa = actual.get("simple") or {}
        at = sa.get("total") or sum(sa.get(k, 0) for k in ("material", "labor", "overhead"))
        bt = sb.get("total") or sum(sb.get(k, 0) for k in ("material", "labor", "overhead"))
        return {
            "mode": "simple",
            "per_process": {},
            "overhead": {},
            "total": at - bt,
        }
    d = _by_process_detailed(product, actual)
    d["mode"] = "detailed"
    d["total"] = sum(p["total"] for p in d["per_process"].values()) + d["overhead"]["total"]
    return d
