/** Visualización 2D de layouts (vista superior XY + lateral XZ). */

const LayoutViz = {
  COLORS: [
    "#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f",
    "#edc948", "#b07aa1", "#ff9da7", "#9c755f", "#bab0ac",
  ],

  baseId(itemId) {
    return String(itemId).split("#")[0];
  },

  colorMap(itemIds) {
    const bases = [...new Set(itemIds.map((id) => this.baseId(id)))].sort();
    const map = {};
    bases.forEach((b, i) => {
      map[b] = this.COLORS[i % this.COLORS.length];
    });
    return map;
  },

  containerList(containers, boxes) {
    return [...(containers || []), ...(boxes || [])];
  },

  dimsFor(containerId, containerList, packedItems) {
    const found = containerList.find((c) => c.id === containerId);
    if (found) {
      return { length: found.length, width: found.width, height: found.height };
    }
    const items = packedItems.filter((p) => p.container_id === containerId);
    let maxX = 0;
    let maxY = 0;
    let maxZ = 0;
    items.forEach((p) => {
      maxX = Math.max(maxX, p.position.x + p.orientation.length);
      maxY = Math.max(maxY, p.position.y + p.orientation.width);
      maxZ = Math.max(maxZ, p.position.z + p.orientation.height);
    });
    return { length: maxX || 100, width: maxY || 80, height: maxZ || 80 };
  },

  pickBestWorstByUtilization(results) {
    const candidates = (results || []).filter(
      (r) => r.solution?.packed_items?.length && r.metrics?.volume_utilization != null
    );
    if (!candidates.length) return null;
    const sorted = [...candidates].sort(
      (a, b) => (b.metrics.volume_utilization || 0) - (a.metrics.volume_utilization || 0)
    );
    const best = sorted[0];
    const worst = sorted[sorted.length - 1];
    return { best, worst, same: best.engine === worst.engine };
  },

  drawLayout(canvas, { frameW, frameH, items, mode, colors }) {
    const ctx = canvas.getContext("2d");
    const pad = 28;
    const maxW = 360;
    const scale = Math.min((maxW - pad * 2) / frameW, (220 - pad * 2) / frameH);
    const drawW = frameW * scale;
    const drawH = frameH * scale;
    canvas.width = maxW;
    canvas.height = 240;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#f8fafc";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const ox = pad;
    const oy = pad;

    ctx.strokeStyle = "#424242";
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.strokeRect(ox, oy, drawW, drawH);
    ctx.setLineDash([]);

    items.forEach((p) => {
      const x = p.position.x;
      const y = p.position.y;
      const z = p.position.z;
      const len = p.orientation.length;
      const wid = p.orientation.width;
      const hei = p.orientation.height;
      let rx;
      let ry;
      let rw;
      let rh;
      if (mode === "top") {
        rx = ox + x * scale;
        ry = oy + y * scale;
        rw = len * scale;
        rh = wid * scale;
      } else {
        rx = ox + x * scale;
        ry = oy + z * scale;
        rw = len * scale;
        rh = hei * scale;
      }
      const color = colors[this.baseId(p.item_id)] || "#94a3b8";
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.88;
      ctx.fillRect(rx, ry, rw, rh);
      ctx.globalAlpha = 1;
      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1.2;
      ctx.strokeRect(rx, ry, rw, rh);
      if (rw > 22 && rh > 14) {
        ctx.fillStyle = "#fff";
        ctx.font = "bold 10px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(this.baseId(p.item_id), rx + rw / 2, ry + rh / 2);
      }
    });

    ctx.fillStyle = "#64748b";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "left";
    if (mode === "top") {
      ctx.fillText("Vista superior (X × Y)", ox, canvas.height - 8);
    } else {
      ctx.fillText("Vista lateral (X × Z)", ox, canvas.height - 8);
    }
  },

  renderContainerBlock(parent, containerId, dims, items, colors) {
    const block = document.createElement("div");
    block.className = "layout-container-block";
    block.innerHTML = `<h4>Contenedor <code>${containerId}</code> <span class="muted">(${dims.length}×${dims.width}×${dims.height})</span></h4>`;
    const views = document.createElement("div");
    views.className = "layout-views";
    const top = document.createElement("canvas");
    const side = document.createElement("canvas");
    views.append(top, side);
    block.appendChild(views);
    parent.appendChild(block);
    this.drawLayout(top, {
      frameW: dims.length,
      frameH: dims.width,
      items,
      mode: "top",
      colors,
    });
    this.drawLayout(side, {
      frameW: dims.length,
      frameH: dims.height,
      items,
      mode: "side",
      colors,
    });
  },

  render(targetEl, { solution, containers, boxes, title }) {
    if (!targetEl) return;
    const packed = solution?.packed_items || [];
    if (!packed.length) {
      targetEl.innerHTML = '<p class="muted">No hay piezas empacadas para visualizar el layout.</p>';
      return;
    }
    const list = this.containerList(containers, boxes);
    const colors = this.colorMap(packed.map((p) => p.item_id));
    const byContainer = {};
    packed.forEach((p) => {
      byContainer[p.container_id] = byContainer[p.container_id] || [];
      byContainer[p.container_id].push(p);
    });

    targetEl.innerHTML = "";
    if (title) {
      const header = document.createElement("div");
      header.className = "layout-header";
      header.innerHTML = `<h3>${title}</h3>`;
      targetEl.appendChild(header);
    }

    const legend = document.createElement("div");
    legend.className = "layout-legend";
    legend.innerHTML = Object.keys(colors)
      .map((b) => `<span class="legend-item"><i style="background:${colors[b]}"></i>${b}</span>`)
      .join("");
    targetEl.appendChild(legend);

    const grid = document.createElement("div");
    grid.className = "layout-grid";
    targetEl.appendChild(grid);

    Object.keys(byContainer)
      .sort()
      .forEach((cid) => {
        const dims = this.dimsFor(cid, list, packed);
        this.renderContainerBlock(grid, cid, dims, byContainer[cid], colors);
      });
  },

  renderCompare(targetEl, results, containers, boxes) {
    if (!targetEl) return;
    const pick = this.pickBestWorstByUtilization(results);
    if (!pick) {
      targetEl.innerHTML = '<p class="muted">No hay soluciones con layout para comparar visualmente.</p>';
      return;
    }
    targetEl.innerHTML = `<h3>Mejor vs peor por utilización de volumen</h3>`;
    if (pick.same) {
      const util = formatPct(pick.best.metrics?.volume_utilization);
      const wrap = document.createElement("div");
      wrap.className = "layout-compare layout-compare-single";
      wrap.innerHTML = `
        <div class="layout-compare-card best">
          <div class="layout-compare-title">
            <span class="badge ok">Mejor y único con layout</span>
            <strong><code>${pick.best.engine}</code></strong>
            <span class="muted">Utilización ${util} · ${pick.best.metrics?.items_packed ?? 0} empacados</span>
          </div>
          <div class="layout-compare-body"></div>
        </div>`;
      targetEl.appendChild(wrap);
      this.render(wrap.querySelector(".layout-compare-body"), {
        solution: pick.best.solution,
        containers,
        boxes,
        title: "",
      });
      return;
    }

    const row = document.createElement("div");
    row.className = "layout-compare";
    targetEl.appendChild(row);

    const cards = [
      { label: "Mejor", cls: "best", result: pick.best },
      { label: "Peor", cls: "worst", result: pick.worst },
    ];

    cards.forEach((card) => {
      const wrap = document.createElement("div");
      wrap.className = `layout-compare-card ${card.cls}`;
      const util = formatPct(card.result.metrics?.volume_utilization);
      wrap.innerHTML = `
        <div class="layout-compare-title">
          <span class="badge ${card.cls === "best" ? "ok" : "warn"}">${card.label}</span>
          <strong><code>${card.result.engine}</code></strong>
          <span class="muted">Utilización ${util} · ${card.result.metrics?.items_packed ?? 0} empacados</span>
        </div>
        <div class="layout-compare-body"></div>`;
      row.appendChild(wrap);
      this.render(wrap.querySelector(".layout-compare-body"), {
        solution: card.result.solution,
        containers,
        boxes,
        title: "",
      });
    });
  },
};
