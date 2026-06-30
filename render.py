"""CLI: read an internal-accounting JSON export, render all product flows
as a single self-contained HTML file."""
from __future__ import annotations

import argparse
from pathlib import Path

from core import graph, loader, svg, wip_store


HTML_HEAD = """<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><title>製造工程フロー</title>
<style>
 body{font-family:-apple-system,'Hiragino Kaku Gothic ProN','Yu Gothic',Meiryo,sans-serif;background:#f7f8fa;color:#1f2933;margin:0}
 .container{max-width:1400px;margin:1.5rem auto;padding:0 1.5rem}
 .card{background:#fff;border:1px solid #e4e7eb;border-radius:8px;padding:1rem 1.5rem;margin-bottom:1rem}
 h1{margin-top:0}h2{border-bottom:1px solid #e4e7eb;padding-bottom:.25rem}
</style></head><body><div class="container"><h1>製造工程フロー（全製品・全期間）</h1>"""

HTML_TAIL = "</div></body></html>"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("--out", type=Path, default=Path("flow.html"))
    args = ap.parse_args()
    data = loader.load(args.input)
    try:
        wip = wip_store.load()
    except Exception:
        wip = []
    parts = [HTML_HEAD]
    for actual in data["actuals"]:
        product = data["products_by_id"].get(actual["product_id"])
        if not product:
            continue
        flow = graph.flow_for_product(product, actual, wip)
        parts.append(f'<section class="card"><h2>{flow["product_name"]} — {flow["period"]}</h2>')
        parts.append(svg.render(flow))
        parts.append(f'<p>総差異: <b>{flow["total_variance"]:+,.0f}</b></p></section>')
    parts.append(HTML_TAIL)
    args.out.write_text("".join(parts), encoding="utf-8")
    print(f"[OK] wrote {args.out}")


if __name__ == "__main__":
    main()
