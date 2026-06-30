"""Pure-Python SVG generator for the process box diagram.

No external dependencies. Nodes are laid out left-to-right; an OH node, if
present, is placed below the main chain centred on the middle process.
"""
from __future__ import annotations

from xml.sax.saxutils import escape

NODE_W = 220
NODE_H = 110
GAP_X = 60
PAD = 20
ROW_GAP = 60


def _color_for(value: float) -> str:
    if value > 0:
        return "#fee2e2"  # unfavourable bg
    if value < 0:
        return "#d1fae5"  # favourable bg
    return "#f3f4f6"


def _border_for(value: float) -> str:
    if value > 0:
        return "#b91c1c"
    if value < 0:
        return "#047857"
    return "#9ca3af"


def _badge(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}¥{value:,.0f}"


def _node_svg(node: dict, x: int, y: int) -> str:
    kind = node.get("kind", "process")
    fill = "#ffffff"
    stroke = "#9ca3af"
    if kind == "process":
        v = node.get("total_var", 0)
        fill = _color_for(v)
        stroke = _border_for(v)
    elif kind == "materials":
        fill = "#eff6ff"; stroke = "#2563eb"
    elif kind == "completion":
        fill = "#ecfdf5"; stroke = "#047857"
    elif kind == "oh":
        v = node.get("total_var", 0)
        fill = _color_for(v); stroke = _border_for(v)

    out = [f'<rect x="{x}" y="{y}" width="{NODE_W}" height="{NODE_H}" rx="8" ry="8" fill="{fill}" stroke="{stroke}" stroke-width="2"/>']
    out.append(f'<text x="{x + NODE_W // 2}" y="{y + 22}" text-anchor="middle" font-size="14" font-weight="700" fill="#1f2933">{escape(node["label"])}</text>')
    for i, line in enumerate(node.get("detail", [])[:3]):
        out.append(f'<text x="{x + 10}" y="{y + 42 + i * 14}" font-size="11" fill="#374151">{escape(line)}</text>')
    if kind == "process" and node.get("total_var") is not None:
        out.append(f'<text x="{x + NODE_W - 10}" y="{y + NODE_H - 8}" text-anchor="end" font-size="12" font-weight="700" fill="{stroke}">{_badge(node["total_var"])}</text>')
    if kind == "process" and node.get("wip"):
        wip = node["wip"]
        out.append(f'<text x="{x + 10}" y="{y + NODE_H - 8}" font-size="11" fill="#6b7280">期首{wip["beginning"]:g} 投入{wip["inputs"]:g} 完成{wip["completed"]:g} 期末{wip["ending"]:g}</text>')
    if kind == "oh" and node.get("total_var") is not None:
        out.append(f'<text x="{x + NODE_W - 10}" y="{y + NODE_H - 8}" text-anchor="end" font-size="12" font-weight="700" fill="{stroke}">{_badge(node["total_var"])}</text>')
    return "".join(out)


def _arrow(x1: int, y1: int, x2: int, y2: int) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#6b7280" stroke-width="2" marker-end="url(#arrow)"/>'
    )


def _wip_box(qty_after: float, x: int, y: int) -> str:
    if not qty_after:
        return ""
    return (
        f'<rect x="{x - 30}" y="{y - 14}" width="60" height="22" rx="4" ry="4" fill="#fef3c7" stroke="#92400e" stroke-width="1"/>'
        f'<text x="{x}" y="{y + 2}" text-anchor="middle" font-size="11" fill="#92400e">WIP {qty_after:g}</text>'
    )


def render(flow: dict) -> str:
    """Render a single product flow as SVG."""
    main_nodes = [n for n in flow["nodes"] if n["kind"] != "oh"]
    oh_nodes = [n for n in flow["nodes"] if n["kind"] == "oh"]
    cols = len(main_nodes)
    rows = 2 if oh_nodes else 1
    width = PAD * 2 + cols * NODE_W + (cols - 1) * GAP_X
    height = PAD * 2 + NODE_H * rows + (ROW_GAP if rows > 1 else 0)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" font-family="-apple-system,Hiragino Kaku Gothic ProN,Yu Gothic,Meiryo,sans-serif">',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#6b7280"/></marker></defs>',
    ]

    # Main row
    y = PAD
    positions = []
    for i, node in enumerate(main_nodes):
        x = PAD + i * (NODE_W + GAP_X)
        positions.append((x, y))
        out.append(_node_svg(node, x, y))

    # Arrows + WIP between process nodes
    for i in range(len(main_nodes) - 1):
        x1 = positions[i][0] + NODE_W
        x2 = positions[i + 1][0]
        yc = y + NODE_H // 2
        out.append(_arrow(x1, yc, x2, yc))
        # If the right-hand node is a process with WIP ending balance, show it as a chip between
        right = main_nodes[i + 1]
        if right.get("kind") == "process" and right.get("wip"):
            out.append(_wip_box(right["wip"]["beginning"], (x1 + x2) // 2, yc))

    # OH row
    if oh_nodes:
        oh_y = PAD + NODE_H + ROW_GAP
        oh_x = PAD + (cols // 2) * (NODE_W + GAP_X)
        out.append(_node_svg(oh_nodes[0], oh_x, oh_y))
        # Connect first process node to OH
        first_process_index = next((i for i, n in enumerate(main_nodes) if n["kind"] == "process"), 0)
        out.append(_arrow(
            positions[first_process_index][0] + NODE_W // 2, y + NODE_H,
            oh_x + NODE_W // 2, oh_y,
        ))

    out.append("</svg>")
    return "".join(out)
