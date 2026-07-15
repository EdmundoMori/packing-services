/** Contexto compartido: tipo de problema, filtrado y instancias showcase. */

const PROBLEM_TYPES = [
  {
    id: "3D_BPP",
    label: "3D Bin Packing",
    hint: "Empaque offline en uno o varios contenedores 3D.",
    showcaseFile: "showcase_3d_bpp_instance.json",
  },
  {
    id: "CONTAINER_LOADING",
    label: "Container Loading",
    hint: "Carga en contenedores con criterios de peso y distribución.",
    showcaseFile: "showcase_container_loading_instance.json",
  },
  {
    id: "SINGLE_CONTAINER_LOADING",
    label: "Single Container Loading",
    hint: "Un único contenedor (p. ej. un camión).",
    showcaseFile: "showcase_single_container_instance.json",
  },
  {
    id: "CARTONIZATION",
    label: "Cartonization",
    hint: "Selección de caja y empaque de un pedido.",
    showcaseFile: "showcase_cartonization_instance.json",
  },
  {
    id: "PALLETIZATION",
    label: "Palletization",
    hint: "Distribución de cajas sobre un pallet.",
    showcaseFile: "showcase_palletization_instance.json",
  },
  {
    id: "STACKING_AWARE",
    label: "Stacking-aware",
    hint: "Apilamiento con soporte, estabilidad y carga máxima.",
    showcaseFile: "showcase_stacking_aware_instance.json",
  },
];

const ProblemContext = {
  storageKey: "ps_problem_type",

  getSelected() {
    return sessionStorage.getItem(this.storageKey) || "";
  },

  setSelected(problemType) {
    if (problemType) sessionStorage.setItem(this.storageKey, problemType);
    else sessionStorage.removeItem(this.storageKey);
  },

  meta(problemType) {
    return PROBLEM_TYPES.find((p) => p.id === problemType) || null;
  },

  filterAlgorithms(algorithms, problemType) {
    if (!problemType) return algorithms;
    return algorithms.filter((algo) => (algo.problem_types || []).includes(problemType));
  },

  mountSelector(selectEl, { includeAll = false, onChange } = {}) {
    const saved = this.getSelected();
    const options = [];
    if (includeAll) options.push(`<option value="">Todos los tipos</option>`);
    options.push(
      ...PROBLEM_TYPES.map(
        (p) => `<option value="${p.id}">${p.label} (${p.id})</option>`
      )
    );
    selectEl.innerHTML = options.join("");
    if (saved && [...selectEl.options].some((o) => o.value === saved)) {
      selectEl.value = saved;
    }
    selectEl.addEventListener("change", () => {
      this.setSelected(selectEl.value);
      if (onChange) onChange(selectEl.value);
    });
    if (onChange) onChange(selectEl.value);
  },

  async loadShowcase(problemType) {
    const meta = this.meta(problemType);
    if (!meta) throw new Error(`Tipo de problema desconocido: ${problemType}`);
    const response = await fetch(`/assets/data/${meta.showcaseFile}`);
    if (!response.ok) throw new Error(`No se pudo cargar la instancia ${meta.showcaseFile}`);
    const data = await response.json();
    const { description, catalog_version, ...payload } = data;
    return { payload, description, catalog_version };
  },

  benchmarkPayloadFromShowcase(showcasePayload, problemType) {
    const copy = JSON.parse(JSON.stringify(showcasePayload));
    copy.problem_type = problemType;
    copy.request_id = `web-benchmark-${problemType.toLowerCase().replace(/_/g, "-")}`;
    delete copy.description;
    delete copy.catalog_version;
    delete copy.engines;
    delete copy.profile;
    return copy;
  },
};

function familyBadge(family) {
  return `<span class="badge info">${family || "—"}</span>`;
}

function truncate(text, max = 120) {
  if (!text) return "Sin descripción.";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}
