/** Integración BED-BPP como única entrada de instancia en Ejecutar / Benchmark. */

const BedBpp = {
  sample: null,
  orderSummaries: [],

  async loadSample() {
    const data = await API.request("/api/v1/datasets/bed-bpp/sample");
    this.sample = data.orders;
    this.refreshSummaries();
    return data;
  },

  refreshSummaries() {
    this.orderSummaries = Object.keys(this.sample || {}).map((oid) => {
      const props = this.sample[oid]?.properties || {};
      const n = Object.keys(this.sample[oid]?.item_sequence || {}).length;
      return {
        order_id: oid,
        order_nr: props.order_nr,
        target: props.target,
        type: props.type,
        n_items: n,
      };
    });
  },

  /** Acepta mapa crudo o wrapper { orders: {...} }. */
  ingestRaw(text) {
    const parsed = JSON.parse(text);
    if (!parsed || typeof parsed !== "object") {
      throw new Error("JSON BED-BPP inválido.");
    }
    const orders = parsed.orders && typeof parsed.orders === "object" ? parsed.orders : parsed;
    if (!orders || typeof orders !== "object" || Array.isArray(orders)) {
      throw new Error("Se esperaba un mapa order_id → { item_sequence, properties }.");
    }
    const first = Object.values(orders)[0];
    if (!first || typeof first.item_sequence !== "object" || typeof first.properties !== "object") {
      throw new Error("Cada pedido debe tener item_sequence y properties (estructura BED-BPP).");
    }
    this.sample = orders;
    this.refreshSummaries();
    return orders;
  },

  fillOrderSelect(selectEl, selectedId) {
    if (!selectEl) return;
    selectEl.innerHTML =
      `<option value="">Selecciona pedido…</option>` +
      this.orderSummaries
        .map((o) => {
          const label = `${o.order_id} · ${o.target || "?"} · ${o.n_items} ítems`;
          const sel = o.order_id === selectedId ? "selected" : "";
          return `<option value="${o.order_id}" ${sel}>${label}</option>`;
        })
        .join("");
  },

  async convert({ orderId, problemType, mode = "execute", parameters, profile, engines, constraints, packingMode }) {
    const body = {
      order_id: orderId,
      problem_type: problemType,
      mode,
      orders: this.sample,
    };
    if (parameters) body.parameters = parameters;
    if (profile) body.profile = profile;
    if (engines) body.engines = engines;
    if (constraints) body.constraints = constraints;
    if (packingMode) body.packing_mode = packingMode;
    return API.request("/api/v1/datasets/bed-bpp/convert", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },

  buildWrapper({ orderId, problemType, parameters, constraints, profile, engines, random_seed, time_limit_seconds, packingMode }) {
    const wrapper = {
      input_format: "bed_bpp",
      problem_type: problemType,
      order_id: orderId,
      orders: this.sample,
    };
    if (parameters) wrapper.parameters = parameters;
    if (constraints) wrapper.constraints = constraints;
    if (profile) wrapper.profile = profile;
    if (engines) wrapper.engines = engines;
    if (packingMode) wrapper.packing_mode = packingMode;
    if (random_seed != null && random_seed !== "") wrapper.random_seed = random_seed;
    if (time_limit_seconds != null && time_limit_seconds !== "") {
      wrapper.time_limit_seconds = time_limit_seconds;
    }
    return wrapper;
  },
};
