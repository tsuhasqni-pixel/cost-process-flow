"""Flask UI for cost-process-flow."""
from __future__ import annotations

import json
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, url_for
from markupsafe import Markup

from core import graph, loader, svg, wip_store

app = Flask(__name__, static_folder="static", template_folder="templates")
HERE = Path(__file__).resolve().parent
DATA_FILE = HERE / "data" / "import.json"


def _data():
    if not DATA_FILE.exists():
        return None
    return loader.load(DATA_FILE)


def _num(form, key: str, default: float = 0.0) -> float:
    v = form.get(key)
    if v is None or v == "":
        return default
    try:
        return float(v)
    except ValueError:
        return default


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        f = request.files.get("file")
        if f:
            DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
            payload = json.load(f.stream)
            DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            return redirect(url_for("flow_list"))
    return render_template("upload.html", loaded=DATA_FILE.exists())


@app.route("/flow")
def flow_list():
    data = _data()
    if not data:
        return redirect(url_for("index"))
    wip = wip_store.load()
    entries = []
    for actual in data["actuals"]:
        p = data["products_by_id"].get(actual["product_id"])
        if not p:
            continue
        flow = graph.flow_for_product(p, actual, wip)
        entries.append(flow)
    return render_template("flow.html", flows=entries, data=data)


@app.route("/flow/<product_id>/<period>")
def flow_detail(product_id: str, period: str):
    data = _data()
    if not data:
        return redirect(url_for("index"))
    product = data["products_by_id"].get(product_id)
    actual = next((a for a in data["actuals"] if a["product_id"] == product_id and a["period"] == period), None)
    if not product or not actual:
        abort(404)
    wip = wip_store.load()
    flow = graph.flow_for_product(product, actual, wip)
    svg_str = svg.render(flow)
    return render_template("flow_detail.html", flow=flow, svg=Markup(svg_str), product=product)


@app.route("/wip", methods=["GET", "POST"])
def wip_page():
    data = _data()
    if not data:
        return redirect(url_for("index"))
    if request.method == "POST":
        entry = {
            "product_id": request.form["product_id"],
            "process": request.form["process"],
            "period": request.form["period"],
            "beginning": _num(request.form, "beginning"),
            "inputs": _num(request.form, "inputs"),
            "completed": _num(request.form, "completed"),
        }
        wip_store.upsert(entry)
        return redirect(url_for("wip_page"))
    # Collect available processes per product
    process_options = {}
    for p in data["products"]:
        process_options[p["id"]] = [l["process"] for l in (p.get("cost_card", {}).get("labors") or [])]
    periods = sorted({a["period"] for a in data["actuals"]})
    return render_template("wip.html", products=data["products"], entries=wip_store.load(),
                           process_options=process_options, periods=periods)


@app.route("/wip/delete", methods=["POST"])
def wip_delete():
    wip_store.delete(request.form["product_id"], request.form["process"], request.form["period"])
    return redirect(url_for("wip_page"))


@app.route("/origin")
def origin_page():
    data = _data()
    if not data:
        return redirect(url_for("index"))
    rows = graph.origin_map(data, wip_store.load())
    return render_template("origin_map.html", rows=rows)


@app.route("/reset", methods=["POST"])
def reset():
    if DATA_FILE.exists():
        DATA_FILE.unlink()
    return redirect(url_for("index"))


@app.template_filter("yen")
def yen(v):
    n = float(v or 0)
    return ("-" if n < 0 else "") + f"¥{abs(n):,.0f}"


@app.template_filter("signed_yen")
def signed_yen(v):
    n = float(v or 0)
    if n > 0:
        return f"+¥{n:,.0f}"
    if n < 0:
        return f"-¥{-n:,.0f}"
    return "¥0"


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=7864, debug=False)
