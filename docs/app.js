/* Static SPA — load internal-accounting JSON + WIP journal, render SVG flows. */
(function () {
  "use strict";

  const LS_KEY = "cost-process-flow/v1";
  let state = load();

  function load() {
    try {
      const raw = localStorage.getItem(LS_KEY);
      const s = raw ? JSON.parse(raw) : {};
      return { products: s.products || [], actuals: s.actuals || [], wip: s.wip || [] };
    } catch (e) { return { products: [], actuals: [], wip: [] }; }
  }
  function save() { localStorage.setItem(LS_KEY, JSON.stringify(state)); }

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const num = (v) => { const n = parseFloat(v); return isNaN(n) ? 0 : n; };
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const signedYen = (v) => { const n = Number(v) || 0; if (n > 0) return "+¥" + Math.round(n).toLocaleString(); if (n < 0) return "-¥" + Math.round(-n).toLocaleString(); return "¥0"; };

  // ---------- variance overlay (port of core/variance_overlay.py) ----------
  function perUnit(perU, so, out) { return so <= 0 ? 0 : (perU / so) * out; }

  function varianceOverlay(product, actual) {
    if (!actual) return { mode: product.mode || "detailed", per_process: {}, overhead: {}, total: 0 };
    if ((product.mode || "detailed") === "simple") {
      const sb = (product.cost_card && product.cost_card.simple_budget) || {};
      const sa = actual.simple || {};
      const at = sa.total || ((sa.material || 0) + (sa.labor || 0) + (sa.overhead || 0));
      const bt = sb.total || ((sb.material || 0) + (sb.labor || 0) + (sb.overhead || 0));
      return { mode: "simple", per_process: {}, overhead: {}, total: at - bt };
    }
    const cc = product.cost_card || {};
    const so = Number(product.std_output) || 1;
    const out = Number(actual.actual_output) || 1;
    const stdLabs = (cc.labors || []).reduce((m, x) => (m[x.process] = x, m), {});
    const actLabs = (actual.labors || []).reduce((m, x) => (m[x.process] = x, m), {});
    const perProcess = {};
    let totAct = 0, totStd = 0;
    for (const name of Array.from(new Set([...Object.keys(stdLabs), ...Object.keys(actLabs)]))) {
      const s = stdLabs[name] || { std_rate: 0, std_hours: 0 };
      const a = actLabs[name] || { actual_rate: 0, actual_hours: 0 };
      const sh = perUnit(s.std_hours, so, out);
      const rateVar = (a.actual_rate - s.std_rate) * a.actual_hours;
      const timeVar = (a.actual_hours - sh) * s.std_rate;
      perProcess[name] = {
        process: name,
        std_rate: s.std_rate, std_hours: s.std_hours,
        actual_rate: a.actual_rate, actual_hours: a.actual_hours,
        rate_var: rateVar, time_var: timeVar, total: rateVar + timeVar,
      };
      totAct += a.actual_hours; totStd += sh;
    }
    const oh = cc.overhead || {};
    const aoh = actual.overhead || {};
    const sfr = oh.normal_hours ? (oh.fixed_budget || 0) / oh.normal_hours : 0;
    const overhead = {
      voh_budget: (aoh.actual_variable || 0) - (oh.var_rate || 0) * totAct,
      voh_efficiency: (oh.var_rate || 0) * (totAct - totStd),
      foh_budget: (aoh.actual_fixed || 0) - (oh.fixed_budget || 0),
      foh_volume: (oh.fixed_budget || 0) - sfr * totStd,
    };
    overhead.total = overhead.voh_budget + overhead.voh_efficiency + overhead.foh_budget + overhead.foh_volume;
    let totalProc = Object.values(perProcess).reduce((s, p) => s + p.total, 0);
    return { mode: "detailed", per_process: perProcess, overhead, total: totalProc + overhead.total };
  }

  // ---------- graph builder ----------
  function flowFor(product, actual, wipEntries) {
    const cc = product.cost_card || {};
    const labors = cc.labors || [];
    const materials = cc.materials || [];
    const overlay = varianceOverlay(product, actual);

    const wipByProcess = {};
    if (wipEntries) {
      for (const w of wipEntries) {
        if (w.product_id !== product.id) continue;
        if (actual && actual.period && w.period && w.period !== actual.period) continue;
        wipByProcess[w.process] = w;
      }
    }

    const nodes = [];
    if (materials.length) {
      nodes.push({ kind: "materials", label: "材料投入",
        detail: materials.map((m) => `${m.name}: ${m.std_qty || 0} @ ¥${(m.std_price || 0).toLocaleString()}`) });
    }
    for (const l of labors) {
      const pv = overlay.per_process[l.process] || {};
      const wip = wipByProcess[l.process];
      nodes.push({
        kind: "process", label: l.process,
        detail: [
          `標準: ${l.std_hours || 0}h × ¥${(l.std_rate || 0).toLocaleString()}`,
          pv.actual_hours !== undefined ? `実際: ${pv.actual_hours}h × ¥${(pv.actual_rate || 0).toLocaleString()}` : "実績未入力",
        ],
        rate_var: pv.rate_var || 0,
        time_var: pv.time_var || 0,
        total_var: pv.total || 0,
        wip: wip ? {
          beginning: wip.beginning || 0,
          inputs: wip.inputs || 0,
          completed: wip.completed || 0,
          ending: (wip.beginning || 0) + (wip.inputs || 0) - (wip.completed || 0),
        } : null,
      });
    }
    if (labors.length) {
      nodes.push({ kind: "completion", label: "完成",
        detail: [`完成数量: ${(actual && actual.actual_output) ?? "?"}`] });
    }
    if (overlay.overhead && Object.keys(overlay.overhead).length) {
      const oh = overlay.overhead;
      nodes.push({
        kind: "oh", label: "製造間接費 (OH)",
        detail: [
          `変動OH予算差異: ${signedYen(oh.voh_budget)}`,
          `変動OH能率差異: ${signedYen(oh.voh_efficiency)}`,
          `固定OH予算差異: ${signedYen(oh.foh_budget)}`,
          `固定OH操業度差異: ${signedYen(oh.foh_volume)}`,
        ],
        total_var: oh.total || 0,
      });
    }
    return {
      product_id: product.id, product_name: product.name,
      period: (actual || {}).period || "",
      mode: product.mode || "detailed",
      nodes, total_variance: overlay.total,
    };
  }

  // ---------- SVG renderer ----------
  const NODE_W = 220, NODE_H = 110, GAP_X = 60, PAD = 20, ROW_GAP = 60;
  const colorFor = (v) => v > 0 ? "#fee2e2" : v < 0 ? "#d1fae5" : "#f3f4f6";
  const borderFor = (v) => v > 0 ? "#b91c1c" : v < 0 ? "#047857" : "#9ca3af";

  function nodeSvg(n, x, y) {
    let fill = "#fff", stroke = "#9ca3af";
    if (n.kind === "process" || n.kind === "oh") { fill = colorFor(n.total_var || 0); stroke = borderFor(n.total_var || 0); }
    else if (n.kind === "materials") { fill = "#eff6ff"; stroke = "#2563eb"; }
    else if (n.kind === "completion") { fill = "#ecfdf5"; stroke = "#047857"; }
    let parts = [`<rect x="${x}" y="${y}" width="${NODE_W}" height="${NODE_H}" rx="8" ry="8" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`];
    parts.push(`<text x="${x + NODE_W / 2}" y="${y + 22}" text-anchor="middle" font-size="14" font-weight="700" fill="#1f2933">${esc(n.label)}</text>`);
    (n.detail || []).slice(0, 3).forEach((line, i) => {
      parts.push(`<text x="${x + 10}" y="${y + 42 + i * 14}" font-size="11" fill="#374151">${esc(line)}</text>`);
    });
    if ((n.kind === "process" || n.kind === "oh") && n.total_var !== undefined) {
      parts.push(`<text x="${x + NODE_W - 10}" y="${y + NODE_H - 8}" text-anchor="end" font-size="12" font-weight="700" fill="${stroke}">${signedYen(n.total_var)}</text>`);
    }
    if (n.kind === "process" && n.wip) {
      parts.push(`<text x="${x + 10}" y="${y + NODE_H - 8}" font-size="11" fill="#6b7280">期首${n.wip.beginning} 投入${n.wip.inputs} 完成${n.wip.completed} 期末${n.wip.ending}</text>`);
    }
    return parts.join("");
  }

  function arrow(x1, y1, x2, y2) {
    return `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="#6b7280" stroke-width="2" marker-end="url(#arrow)"/>`;
  }
  function wipBox(qty, x, y) {
    if (!qty) return "";
    return `<rect x="${x - 30}" y="${y - 14}" width="60" height="22" rx="4" ry="4" fill="#fef3c7" stroke="#92400e" stroke-width="1"/>
            <text x="${x}" y="${y + 2}" text-anchor="middle" font-size="11" fill="#92400e">WIP ${qty}</text>`;
  }

  function renderSvg(flow) {
    const main = flow.nodes.filter((n) => n.kind !== "oh");
    const oh = flow.nodes.filter((n) => n.kind === "oh");
    const cols = main.length;
    const rows = oh.length ? 2 : 1;
    const W = PAD * 2 + cols * NODE_W + Math.max(0, cols - 1) * GAP_X;
    const H = PAD * 2 + NODE_H * rows + (rows > 1 ? ROW_GAP : 0);
    let s = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="100%" height="${H}" font-family="-apple-system,Hiragino Kaku Gothic ProN,Yu Gothic,Meiryo,sans-serif">`;
    s += '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#6b7280"/></marker></defs>';
    const positions = [];
    const y = PAD;
    main.forEach((n, i) => {
      const x = PAD + i * (NODE_W + GAP_X);
      positions.push([x, y]);
      s += nodeSvg(n, x, y);
    });
    for (let i = 0; i < main.length - 1; i++) {
      const x1 = positions[i][0] + NODE_W;
      const x2 = positions[i + 1][0];
      const yc = y + NODE_H / 2;
      s += arrow(x1, yc, x2, yc);
      const right = main[i + 1];
      if (right.kind === "process" && right.wip) {
        s += wipBox(right.wip.beginning, (x1 + x2) / 2, yc);
      }
    }
    if (oh.length) {
      const ohY = PAD + NODE_H + ROW_GAP;
      const ohX = PAD + Math.floor(cols / 2) * (NODE_W + GAP_X);
      s += nodeSvg(oh[0], ohX, ohY);
      const firstProc = main.findIndex((n) => n.kind === "process");
      const idx = firstProc < 0 ? 0 : firstProc;
      s += arrow(positions[idx][0] + NODE_W / 2, y + NODE_H, ohX + NODE_W / 2, ohY);
    }
    s += "</svg>";
    return s;
  }

  function originMap() {
    const agg = {};
    const byId = state.products.reduce((m, p) => (m[p.id] = p, m), {});
    for (const actual of state.actuals) {
      const p = byId[actual.product_id];
      if (!p || (p.mode || "detailed") !== "detailed") continue;
      const flow = flowFor(p, actual, state.wip);
      for (const n of flow.nodes) {
        if (n.kind !== "process") continue;
        const e = (agg[n.label] ||= { process: n.label, appearances: 0, rate_var: 0, time_var: 0, total_var: 0, products: new Set() });
        e.appearances += 1;
        e.rate_var += n.rate_var || 0;
        e.time_var += n.time_var || 0;
        e.total_var += n.total_var || 0;
        e.products.add(p.name);
      }
    }
    return Object.values(agg).map((e) => ({ ...e, products: Array.from(e.products) })).sort((a, b) => b.total_var - a.total_var);
  }

  // ---------- rendering ----------
  function showTab(name) { $$(".tab").forEach((el) => (el.hidden = el.id !== "tab-" + name)); }
  document.addEventListener("click", (e) => {
    const t = e.target.closest("[data-tab]");
    if (t) { e.preventDefault(); render(t.dataset.tab); }
  });

  function renderFlowList() {
    const byId = state.products.reduce((m, p) => (m[p.id] = p, m), {});
    const rows = state.actuals.map((a) => {
      const p = byId[a.product_id]; if (!p) return null;
      return flowFor(p, a, state.wip);
    }).filter(Boolean);
    if (!rows.length) { $("#flowList").innerHTML = `<p class="muted">実績データがありません。</p>`; return; }
    $("#flowList").innerHTML = `<table class="grid"><thead><tr><th>製品</th><th>モード</th><th>期間</th><th>工程数</th><th>総差異</th><th>操作</th></tr></thead><tbody>${rows.map((f) => `
      <tr><td>${esc(f.product_name)}</td><td>${f.mode === "detailed" ? "詳細" : "簡易"}</td><td>${esc(f.period)}</td>
          <td class="right">${f.nodes.filter((n) => n.kind === "process").length}</td>
          <td class="right">${signedYen(f.total_variance)}</td>
          <td><button class="btn ghost" type="button" data-flow='${JSON.stringify({ pid: f.product_id, period: f.period })}'>フロー図を見る</button></td></tr>`).join("")}</tbody></table>`;
  }

  function showFlowDetail(pid, period) {
    const p = state.products.find((x) => x.id === pid);
    const a = state.actuals.find((x) => x.product_id === pid && x.period === period);
    if (!p || !a) return;
    const flow = flowFor(p, a, state.wip);
    $("#flowDetailCard").hidden = false;
    $("#flowDetailTitle").textContent = `${flow.product_name} — ${flow.period}`;
    $("#flowSvg").innerHTML = renderSvg(flow);
    $("#flowDetailTable").innerHTML = `<h3>工程別差異</h3><table class="grid"><thead><tr><th>工程</th><th>賃率差異</th><th>時間差異</th><th>合計</th><th>期首</th><th>投入</th><th>完成</th><th>期末</th></tr></thead><tbody>${flow.nodes.filter((n) => n.kind === "process").map((n) => `
      <tr><td>${esc(n.label)}</td>
          <td class="right">${signedYen(n.rate_var)}</td>
          <td class="right">${signedYen(n.time_var)}</td>
          <td class="right">${signedYen(n.total_var)}</td>
          <td class="right">${n.wip ? n.wip.beginning : "—"}</td>
          <td class="right">${n.wip ? n.wip.inputs : "—"}</td>
          <td class="right">${n.wip ? n.wip.completed : "—"}</td>
          <td class="right">${n.wip ? n.wip.ending : "—"}</td></tr>`).join("")}</tbody></table>`;
    $("#flowDetailCard").scrollIntoView({ behavior: "smooth" });
  }

  function renderWipForm() {
    const prodSel = $("#wipProd");
    const procSel = $("#wipProc");
    const periodSel = $("#wipPeriod");
    prodSel.innerHTML = state.products.map((p) => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join("");
    function refreshProcs() {
      const p = state.products.find((x) => x.id === prodSel.value);
      const procs = (p && p.cost_card && p.cost_card.labors || []).map((l) => l.process);
      procSel.innerHTML = procs.map((x) => `<option value="${esc(x)}">${esc(x)}</option>`).join("");
    }
    prodSel.onchange = refreshProcs;
    refreshProcs();
    const periods = Array.from(new Set(state.actuals.map((a) => a.period))).sort();
    periodSel.innerHTML = periods.map((p) => `<option value="${esc(p)}">${esc(p)}</option>`).join("");
  }

  function renderWipList() {
    if (!state.wip.length) { $("#wipList").innerHTML = `<p class="muted">エントリがありません。</p>`; return; }
    const byId = state.products.reduce((m, p) => (m[p.id] = p, m), {});
    $("#wipList").innerHTML = `<table class="grid"><thead><tr><th>製品</th><th>工程</th><th>期間</th><th>期首</th><th>投入</th><th>完成</th><th>期末</th><th></th></tr></thead><tbody>${state.wip.map((e) => `
      <tr><td>${esc((byId[e.product_id] || {}).name || e.product_id)}</td>
          <td>${esc(e.process)}</td><td>${esc(e.period)}</td>
          <td class="right">${e.beginning}</td><td class="right">${e.inputs}</td>
          <td class="right">${e.completed}</td>
          <td class="right">${(e.beginning || 0) + (e.inputs || 0) - (e.completed || 0)}</td>
          <td><button class="btn danger" type="button" data-wip-del='${JSON.stringify(e)}'>削除</button></td></tr>`).join("")}</tbody></table>`;
  }

  function renderOrigin() {
    const rows = originMap();
    if (!rows.length) { $("#originContent").innerHTML = `<p class="muted">詳細モードの実績データがありません。</p>`; return; }
    $("#originContent").innerHTML = `<table class="grid"><thead><tr><th>工程</th><th>登場</th><th>賃率差異</th><th>時間差異</th><th>合計</th><th>関連製品</th></tr></thead><tbody>${rows.map((r) => `
      <tr><td>${esc(r.process)}</td><td class="right">${r.appearances}</td>
          <td class="right">${signedYen(r.rate_var)}</td>
          <td class="right">${signedYen(r.time_var)}</td>
          <td class="right">${signedYen(r.total_var)}</td>
          <td class="small muted">${r.products.map(esc).join("、")}</td></tr>`).join("")}</tbody></table>`;
  }

  function render(tab) {
    if (!state.products.length) { showTab("empty"); return; }
    if (!tab) tab = "flow";
    renderFlowList();
    renderWipForm();
    renderWipList();
    renderOrigin();
    showTab(tab);
  }

  // ---------- events ----------
  document.addEventListener("click", (e) => {
    const f = e.target.closest("[data-flow]");
    if (f) { const o = JSON.parse(f.dataset.flow); showFlowDetail(o.pid, o.period); return; }
    const d = e.target.closest("[data-wip-del]");
    if (d) {
      if (!confirm("削除します。よろしいですか?")) return;
      const o = JSON.parse(d.dataset.wipDel);
      state.wip = state.wip.filter((x) => !(x.product_id === o.product_id && x.process === o.process && x.period === o.period));
      save(); render("wip");
    }
  });

  $("#wipForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const form = e.currentTarget;
    const entry = {
      product_id: form.elements["product_id"].value,
      process: form.elements["process"].value,
      period: form.elements["period"].value,
      beginning: num(form.elements["beginning"].value),
      inputs: num(form.elements["inputs"].value),
      completed: num(form.elements["completed"].value),
    };
    if (!entry.product_id || !entry.process || !entry.period) return;
    const idx = state.wip.findIndex((x) => x.product_id === entry.product_id && x.process === entry.process && x.period === entry.period);
    if (idx >= 0) state.wip[idx] = entry; else state.wip.push(entry);
    save(); render("wip");
  });

  $("#fileImport").addEventListener("change", (e) => {
    const f = e.target.files[0]; if (!f) return;
    const r = new FileReader();
    r.onload = () => {
      try {
        const s = JSON.parse(r.result);
        state.products = s.products || [];
        state.actuals = s.actuals || [];
        save(); render("flow");
      } catch (err) { alert("JSON 読み込みエラー: " + err); }
    };
    r.readAsText(f); e.target.value = "";
  });

  $("#btnReset").addEventListener("click", () => {
    if (!confirm("読込済みデータを破棄します（WIP ジャーナルも消えます）。よろしいですか?")) return;
    state = { products: [], actuals: [], wip: [] }; save(); render();
  });

  render();
})();
