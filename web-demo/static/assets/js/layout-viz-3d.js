/** Visualización 3D de layouts (Plotly Mesh3d), adaptada del enfoque D-Wave. */

const LayoutViz3D = {
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
    let maxX = 0;
    let maxY = 0;
    let maxZ = 0;
    packedItems
      .filter((p) => p.container_id === containerId)
      .forEach((p) => {
        maxX = Math.max(maxX, p.position.x + p.orientation.length);
        maxY = Math.max(maxY, p.position.y + p.orientation.width);
        maxZ = Math.max(maxZ, p.position.z + p.orientation.height);
      });
    return { length: maxX || 100, width: maxY || 80, height: maxZ || 80 };
  },

  /** Vértices únicos de un cuboide (origen + tamaño). */
  cuboidMesh(origin, size) {
    const [ox, oy, oz] = origin;
    const [sx, sy, sz] = size;
    const corners = [
      [ox, oy, oz],
      [ox + sx, oy, oz],
      [ox + sx, oy + sy, oz],
      [ox, oy + sy, oz],
      [ox, oy, oz + sz],
      [ox + sx, oy, oz + sz],
      [ox + sx, oy + sy, oz + sz],
      [ox, oy + sy, oz + sz],
    ];
    // Caras trianguladas (índices de corners)
    const faces = [
      [0, 1, 2], [0, 2, 3], // z=0
      [4, 5, 6], [4, 6, 7], // z=sz
      [0, 1, 5], [0, 5, 4], // y=0
      [3, 2, 6], [3, 6, 7], // y=sy
      [0, 3, 7], [0, 7, 4], // x=0
      [1, 2, 6], [1, 6, 5], // x=sx
    ];
    const x = [];
    const y = [];
    const z = [];
    const i = [];
    const j = [];
    const k = [];
    corners.forEach((c) => {
      x.push(c[0]);
      y.push(c[1]);
      z.push(c[2]);
    });
    faces.forEach((f) => {
      i.push(f[0]);
      j.push(f[1]);
      k.push(f[2]);
    });
    return { x, y, z, i, j, k };
  },

  wireframeTrace(length, width, height) {
    const corners = [
      [0, 0, 0],
      [length, 0, 0],
      [length, width, 0],
      [0, width, 0],
      [0, 0, height],
      [length, 0, height],
      [length, width, height],
      [0, width, height],
    ];
    const edges = [
      [0, 1], [1, 2], [2, 3], [3, 0],
      [4, 5], [5, 6], [6, 7], [7, 4],
      [0, 4], [1, 5], [2, 6], [3, 7],
    ];
    const x = [];
    const y = [];
    const z = [];
    edges.forEach(([a, b]) => {
      x.push(corners[a][0], corners[b][0], null);
      y.push(corners[a][1], corners[b][1], null);
      z.push(corners[a][2], corners[b][2], null);
    });
    return {
      type: "scatter3d",
      x,
      y,
      z,
      mode: "lines",
      name: "Contenedor",
      line: { color: "#b91c1c", width: 5 },
      hoverinfo: "skip",
      showlegend: true,
    };
  },

  plotContainer(divEl, containerId, dims, items, colors, title) {
    if (typeof Plotly === "undefined") {
      divEl.innerHTML = '<p class="muted">Plotly.js no está cargado; no se puede mostrar el layout 3D.</p>';
      return;
    }
    const traces = items.map((p) => {
      const mesh = this.cuboidMesh(
        [p.position.x, p.position.y, p.position.z],
        [p.orientation.length, p.orientation.width, p.orientation.height]
      );
      const sku = this.baseId(p.item_id);
      return {
        type: "mesh3d",
        ...mesh,
        name: p.item_id,
        color: colors[sku] || "#94a3b8",
        opacity: 0.88,
        flatshading: true,
        showlegend: true,
        hovertext: p.item_id,
        hoverinfo: "text",
      };
    });
    traces.push(this.wireframeTrace(dims.length, dims.width, dims.height));

    const layout = {
      title: { text: title || `Layout 3D — ${containerId}`, font: { size: 14 } },
      margin: { l: 0, r: 0, t: 36, b: 0 },
      height: 360,
      scene: {
        xaxis: { title: "X (largo)", range: [0, dims.length * 1.05] },
        yaxis: { title: "Y (ancho)", range: [0, dims.width * 1.05] },
        zaxis: { title: "Z (alto)", range: [0, dims.height * 1.05] },
        aspectmode: "data",
      },
      showlegend: true,
    };
    Plotly.newPlot(divEl, traces, layout, { responsive: true, displayModeBar: true });
  },

  render(targetEl, { solution, containers, boxes, title }) {
    if (!targetEl) return;
    const packed = solution?.packed_items || [];
    if (!packed.length) {
      targetEl.innerHTML = '<p class="muted">No hay piezas empacadas para visualizar en 3D.</p>';
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

    const grid = document.createElement("div");
    grid.className = "layout-grid layout-grid-3d";
    targetEl.appendChild(grid);

    Object.keys(byContainer)
      .sort()
      .forEach((cid) => {
        const dims = this.dimsFor(cid, list, packed);
        const block = document.createElement("div");
        block.className = "layout-container-block";
        block.innerHTML = `<h4>3D · Contenedor <code>${cid}</code> <span class="muted">(${dims.length}×${dims.width}×${dims.height})</span></h4>`;
        const plotDiv = document.createElement("div");
        plotDiv.className = "layout-3d-plot";
        block.appendChild(plotDiv);
        grid.appendChild(block);
        this.plotContainer(plotDiv, cid, dims, byContainer[cid], colors, `3D — ${cid}`);
      });
  },

  renderCompare(targetEl, results, containers, boxes) {
    if (!targetEl) return;
    const pick = typeof LayoutViz !== "undefined" ? LayoutViz.pickBestWorstByUtilization(results) : null;
    if (!pick) {
      targetEl.innerHTML = '<p class="muted">No hay soluciones con layout 3D para comparar.</p>';
      return;
    }
    targetEl.innerHTML = `<h3>Vista 3D — mejor vs peor (utilización %)</h3>`;
    if (pick.same) {
      const wrap = document.createElement("div");
      wrap.className = "layout-compare layout-compare-single";
      wrap.innerHTML = `
        <div class="layout-compare-card best">
          <div class="layout-compare-title">
            <span class="badge ok">Mejor y único</span>
            <strong><code>${pick.best.engine}</code></strong>
          </div>
          <div class="layout-compare-body-3d"></div>
        </div>`;
      targetEl.appendChild(wrap);
      this.render(wrap.querySelector(".layout-compare-body-3d"), {
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
    [
      { label: "Mejor", cls: "best", result: pick.best },
      { label: "Peor", cls: "worst", result: pick.worst },
    ].forEach((card) => {
      const wrap = document.createElement("div");
      wrap.className = `layout-compare-card ${card.cls}`;
      wrap.innerHTML = `
        <div class="layout-compare-title">
          <span class="badge ${card.cls === "best" ? "ok" : "warn"}">${card.label}</span>
          <strong><code>${card.result.engine}</code></strong>
        </div>
        <div class="layout-compare-body-3d"></div>`;
      row.appendChild(wrap);
      this.render(wrap.querySelector(".layout-compare-body-3d"), {
        solution: card.result.solution,
        containers,
        boxes,
        title: "",
      });
    });
  },
};

// Exponer en globalThis para Node (tests) y browsers.
if (typeof globalThis !== "undefined") {
  globalThis.LayoutViz3D = LayoutViz3D;
}
