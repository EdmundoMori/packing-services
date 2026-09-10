/** Contexto compartido: tipos de problema y filtrado (entrada UI = BED-BPP). */

/** Tipos compatibles con entrada BED-BPP en Ejecutar / Benchmark. */
const BED_BPP_PROBLEM_TYPES = [
  {
    id: "PALLETIZATION",
    label: "Palletization",
    hint: "Distribución sobre pallet/rollcontainer (encaje natural con BED-BPP).",
  },
  {
    id: "STACKING_AWARE",
    label: "Stacking-aware",
    hint: "Apilamiento con soporte y estabilidad sobre el target BED-BPP.",
  },
  {
    id: "SINGLE_CONTAINER_LOADING",
    label: "Single Container Loading",
    hint: "Un único contenedor = target del pedido BED-BPP.",
  },
  {
    id: "3D_BPP",
    label: "3D Bin Packing",
    hint: "Empaque 3D usando el target del pedido como contenedor.",
  },
  {
    id: "CONTAINER_LOADING",
    label: "Container Loading",
    hint: "Carga en contenedor con el target BED-BPP.",
  },
];

/** Catálogo completo (p. ej. página Catálogo); CARTONIZATION no usa BED-BPP. */
const PROBLEM_TYPES = [
  ...BED_BPP_PROBLEM_TYPES,
  {
    id: "CARTONIZATION",
    label: "Cartonization",
    hint: "Selección de caja (requiere catálogo de boxes; no usa BED-BPP).",
    showcaseFile: "showcase_cartonization_instance.json",
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

  mountSelector(selectEl, { includeAll = false, bedBppOnly = false, onChange } = {}) {
    const saved = this.getSelected();
    const source = bedBppOnly ? BED_BPP_PROBLEM_TYPES : PROBLEM_TYPES;
    const options = [];
    if (includeAll) options.push(`<option value="">Todos los tipos</option>`);
    options.push(
      ...source.map((p) => `<option value="${p.id}">${p.label} (${p.id})</option>`)
    );
    selectEl.innerHTML = options.join("");
    const fallback = bedBppOnly ? "PALLETIZATION" : "";
    if (saved && [...selectEl.options].some((o) => o.value === saved)) {
      selectEl.value = saved;
    } else if (fallback && [...selectEl.options].some((o) => o.value === fallback)) {
      selectEl.value = fallback;
      this.setSelected(fallback);
    }
    selectEl.addEventListener("change", () => {
      this.setSelected(selectEl.value);
      if (onChange) onChange(selectEl.value);
    });
    if (onChange) onChange(selectEl.value);
  },
};

function familyBadge(family) {
  return `<span class="badge info">${family || "—"}</span>`;
}

function truncate(text, max = 120) {
  if (!text) return "Sin descripción.";
  return text.length > max ? `${text.slice(0, max)}…` : text;
}
