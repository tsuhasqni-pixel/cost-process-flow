"""Graph and SVG sanity tests."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import graph, svg, variance_overlay


PRODUCT = {
    "id": "P1", "name": "テスト製品", "mode": "detailed", "std_output": 1.0,
    "cost_card": {
        "materials": [{"name": "鋼材A", "std_price": 100, "std_qty": 50}],
        "labors": [
            {"process": "切断", "std_rate": 1200, "std_hours": 4},
            {"process": "機械加工", "std_rate": 1500, "std_hours": 6},
        ],
        "overhead": {"var_rate": 500, "fixed_budget": 100000, "normal_hours": 100},
        "simple_budget": {"total": 0, "material": 0, "labor": 0, "overhead": 0},
    },
}
ACTUAL = {
    "product_id": "P1", "period": "2026-Q1", "actual_output": 1.0,
    "materials": [{"name": "鋼材A", "actual_price": 110, "actual_qty": 55}],
    "labors": [
        {"process": "切断", "actual_rate": 1250, "actual_hours": 4.5},
        {"process": "機械加工", "actual_rate": 1480, "actual_hours": 6.5},
    ],
    "overhead": {"actual_variable": 6000, "actual_fixed": 102000},
    "simple": {"total": 0, "material": 0, "labor": 0, "overhead": 0},
}


def test_variance_overlay_per_process():
    o = variance_overlay.variance_overlay(PRODUCT, ACTUAL)
    # 切断: rate_var = (1250-1200)*4.5 = 225 ; time_var = (4.5-4)*1200 = 600
    p = o["per_process"]["切断"]
    assert abs(p["rate_var"] - 225) < 1e-6
    assert abs(p["time_var"] - 600) < 1e-6
    assert abs(p["total"] - 825) < 1e-6


def test_flow_for_product_has_materials_processes_completion_oh():
    flow = graph.flow_for_product(PRODUCT, ACTUAL)
    kinds = [n["kind"] for n in flow["nodes"]]
    assert "materials" in kinds
    assert "completion" in kinds
    assert "oh" in kinds
    assert kinds.count("process") == 2


def test_svg_render_returns_svg_markup():
    flow = graph.flow_for_product(PRODUCT, ACTUAL)
    s = svg.render(flow)
    assert s.startswith("<svg")
    assert "切断" in s
    assert "機械加工" in s
    assert "材料投入" in s
    # arrow marker defined
    assert 'id="arrow"' in s


def test_wip_balance_propagates():
    wip = [{"product_id": "P1", "process": "機械加工", "period": "2026-Q1",
            "beginning": 10, "inputs": 5, "completed": 12}]
    flow = graph.flow_for_product(PRODUCT, ACTUAL, wip)
    mach = next(n for n in flow["nodes"] if n["kind"] == "process" and n["label"] == "機械加工")
    assert mach["wip"]["beginning"] == 10
    assert mach["wip"]["ending"] == 10 + 5 - 12  # 3


def test_origin_map_aggregates_across_products():
    PRODUCT_B = {**PRODUCT, "id": "P2", "name": "製品B"}
    data = {
        "products": [PRODUCT, PRODUCT_B], "actuals": [ACTUAL, {**ACTUAL, "product_id": "P2"}],
        "products_by_id": {"P1": PRODUCT, "P2": PRODUCT_B},
    }
    rows = graph.origin_map(data)
    proc_names = {r["process"] for r in rows}
    assert "切断" in proc_names and "機械加工" in proc_names
    cut = next(r for r in rows if r["process"] == "切断")
    assert cut["appearances"] == 2
    assert "テスト製品" in cut["products"] and "製品B" in cut["products"]


if __name__ == "__main__":
    test_variance_overlay_per_process()
    test_flow_for_product_has_materials_processes_completion_oh()
    test_svg_render_returns_svg_markup()
    test_wip_balance_propagates()
    test_origin_map_aggregates_across_products()
    print("OK")
