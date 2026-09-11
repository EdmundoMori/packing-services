let allAlgorithms = [];
let filtered = [];
let selectedName = null;
let detailsCache = {};

function currentPackingMode() {
  return $("packing-mode-select")?.value || "offline";
}

function modeBadges(modes) {
  return (modes || [])
    .map((m) => `<span class="badge ${m === "online" ? "mode-online" : "mode-offline"}">${m}</span>`)
    .join(" ");
}

function updateHint(problemType) {
  const meta = ProblemContext.meta(problemType);
  const packingMode = currentPackingMode();
  const onlyOnline = allAlgorithms.filter((algo) => {
    const modes = algo.packing_modes || ["offline"];
    return modes.includes("online") && !modes.includes("offline");
  }).length;
  let extra = "";
  if (packingMode === "offline" && onlyOnline) {
    extra = ` ${onlyOnline} algoritmo(s) solo-online ocultos (cambia a Online).`;
  }
  $("problem-hint").textContent = (meta ? meta.hint : "Mostrando todos los algoritmos implementados. Elige un tipo para filtrar.") + extra;
}

function renderCards() {
  const grid = $("model-grid");
  const search = $("filter-search").value.trim().toLowerCase();
  const visible = filtered.filter((algo) => {
    if (!search) return true;
    const hay = `${algo.name} ${algo.display_name} ${algo.description || ""}`.toLowerCase();
    return hay.includes(search);
  });
  $("catalog-count").textContent = `${visible.length} modelos`;
  if (!visible.length) {
    grid.innerHTML = '<p class="muted">No hay algoritmos para este tipo de problema.</p>';
    return;
  }
  grid.innerHTML = visible
    .map(
      (algo) => `
      <article class="model-card ${algo.name === selectedName ? "selected" : ""}" data-name="${algo.name}">
        <h3>${algo.display_name}</h3>
        <code>${algo.name}</code>
        <p>${modeBadges(algo.packing_modes)} ${familyBadge(algo.algorithm_family)}</p>
        <p>${truncate(algo.description, 160)}</p>
      </article>`
    )
    .join("");
  grid.querySelectorAll(".model-card").forEach((card) => {
    card.addEventListener("click", () => selectModel(card.dataset.name));
  });
}

async function selectModel(name) {
  selectedName = name;
  renderCards();
  const panel = $("detail-panel");
  panel.hidden = false;
  $("detail-title").textContent = name;
  $("detail-body").innerHTML = '<p class="muted">Cargando detalle…</p>';
  const packingMode = currentPackingMode();
  const cacheKey = `${name}:${packingMode}`;
  try {
    if (!detailsCache[cacheKey]) {
      detailsCache[cacheKey] = await API.getAlgorithm(name, packingMode);
    }
    const d = detailsCache[cacheKey];
    const params = Object.entries(d.parameters || {})
      .map(([k, v]) => `<li><code>${k}</code>: ${v}</li>`)
      .join("");
    const defaults = Object.entries(d.default_parameters || {})
      .map(([k, v]) => `<li><code>${k}</code> = <code>${typeof v === "string" ? v : JSON.stringify(v)}</code></li>`)
      .join("");
    $("detail-body").innerHTML = `
      <p>${d.description || "—"}</p>
      <dl class="detail-grid">
        <div><dt>Display name</dt><dd>${d.display_name}</dd></div>
        <div><dt>Familia</dt><dd>${d.algorithm_family}</dd></div>
        <div><dt>Modos</dt><dd>${modeBadges(d.packing_modes)}</dd></div>
        <div><dt>Tipos de problema</dt><dd>${(d.problem_types || []).join(", ")}</dd></div>
        <div><dt>Determinista</dt><dd>${d.deterministic ? "Sí" : "No"}</dd></div>
        <div><dt>Esquema entrada</dt><dd><code>${d.input_schema}</code></dd></div>
        <div><dt>Endpoint</dt><dd><code>${d.execution_endpoint}</code></dd></div>
      </dl>
      ${defaults ? `<h3>Valores por defecto</h3><ul id="detail-defaults">${defaults}</ul>` : ""}
      ${params ? `<h3>Parámetros</h3><ul>${params}</ul>` : ""}
      ${(d.limitations || []).length ? `<h3>Limitaciones</h3><ul>${d.limitations.map((l) => `<li>${l}</li>`).join("")}</ul>` : ""}`;
    const pt = $("problem-type-select").value || (d.problem_types || [])[0] || "";
    $("detail-execute-link").href =
      `execute.html?problem_type=${encodeURIComponent(pt)}` +
      `&algorithm=${encodeURIComponent(name)}` +
      `&packing_mode=${encodeURIComponent(packingMode)}`;
  } catch (err) {
    $("detail-body").innerHTML = `<p class="alert error">${err.message}</p>`;
  }
}

function onProblemChange(problemType) {
  updateHint(problemType);
  filtered = ProblemContext.filterAlgorithms(
    allAlgorithms,
    problemType,
    currentPackingMode()
  );
  selectedName = null;
  $("detail-panel").hidden = true;
  renderCards();
}

async function initCatalog() {
  setActiveNav("catalog");
  const alertBox = $("catalog-alert");
  try {
    allAlgorithms = await API.listAlgorithms({ status: "implemented" });
    allAlgorithms.sort((a, b) => a.display_name.localeCompare(b.display_name));
    ProblemContext.mountPackingMode($("packing-mode-select"), () =>
      onProblemChange($("problem-type-select").value)
    );
    ProblemContext.mountSelector($("problem-type-select"), {
      includeAll: true,
      onChange: onProblemChange,
    });
    $("filter-search").addEventListener("input", renderCards);
    const params = new URLSearchParams(window.location.search);
    const presetAlgo = params.get("algorithm");
    if (presetAlgo) await selectModel(presetAlgo);
  } catch (err) {
    showAlert(alertBox, err.message);
  }
}

document.addEventListener("DOMContentLoaded", initCatalog);
