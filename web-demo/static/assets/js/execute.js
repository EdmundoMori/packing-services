let implemented = [];
let currentDetail = null;
let configPayload = {};
let lastConvertedInput = null;
let previewSeq = 0;

function initResultTabs() {
  document.querySelectorAll(".result-tabs .tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const section = btn.closest("section");
      section.querySelectorAll(".result-tabs .tab-btn").forEach((b) => b.classList.remove("active"));
      section.querySelectorAll("[id^='result-tab-']").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      $(`result-tab-${btn.dataset.resultTab}`).classList.add("active");
    });
  });
}

function updateHint(problemType) {
  const meta = ProblemContext.meta(problemType);
  $("problem-hint").textContent = meta ? meta.hint : "";
}

function currentPackingMode() {
  return $("packing-mode-select")?.value || "offline";
}

function populateAlgorithms(problemType) {
  const select = $("algorithm-select");
  const compatible = ProblemContext.filterAlgorithms(
    implemented,
    problemType,
    currentPackingMode()
  );
  select.innerHTML =
    `<option value="">Selecciona algoritmo…</option>` +
    compatible
      .map((a) => `<option value="${a.name}">${a.display_name} (${a.name})</option>`)
      .join("");
  if (!compatible.length) {
    $("algo-meta").innerHTML = '<p class="muted">No hay algoritmos para este tipo de problema.</p>';
  }
}

function renderAlgorithmMeta(detail) {
  $("algo-meta").innerHTML = `
    <p><strong>${detail.display_name}</strong> — ${truncate(detail.description, 200)}</p>
    <p>${familyBadge(detail.algorithm_family)} <span class="badge ok">${detail.status}</span></p>`;
}

function currentConfig() {
  if (FormBuilder.container && FormBuilder.mode === "config") {
    FormBuilder.applyParameters();
    return {
      parameters: { ...(FormBuilder.payload.parameters || {}) },
      constraints: { ...(FormBuilder.payload.constraints || {}) },
      random_seed: FormBuilder.payload.random_seed,
      time_limit_seconds: FormBuilder.payload.time_limit_seconds,
    };
  }
  return {
    parameters: { ...(configPayload.parameters || {}) },
    constraints: { ...(configPayload.constraints || {}) },
    random_seed: configPayload.random_seed,
    time_limit_seconds: configPayload.time_limit_seconds,
  };
}

function mountConfigForm() {
  FormBuilder.mountConfig($("params-form"), configPayload, currentDetail?.parameters || {}, (payload) => {
    configPayload = payload;
  });
}

function clearAlgorithmInputPreview(message) {
  lastConvertedInput = null;
  $("algorithm-input-json").value = "";
  $("algorithm-input-json").placeholder = message || "Selecciona un pedido para ver la entrada convertida…";
}

async function refreshAlgorithmInputPreview({ silent = false } = {}) {
  const alertBox = $("execute-alert");
  const orderId = $("bedbpp-order-select").value;
  const problemType = $("problem-type-select").value || "PALLETIZATION";
  if (!orderId) {
    clearAlgorithmInputPreview();
    $("bedbpp-hint").textContent = BedBpp.sample
      ? `${BedBpp.orderSummaries.length} pedidos en el dataset. Elige uno para ver la entrada del algoritmo.`
      : "";
    return null;
  }
  if (!BedBpp.sample) {
    clearAlgorithmInputPreview("Carga la muestra o pega un dataset BED-BPP.");
    return null;
  }

  const seq = ++previewSeq;
  const cfg = currentConfig();
  try {
    const converted = await BedBpp.convert({
      orderId,
      problemType,
      mode: "execute",
      parameters: cfg.parameters,
      constraints: cfg.constraints,
      packingMode: currentPackingMode(),
    });
    if (seq !== previewSeq) return null;

    const input = { ...converted.input };
    input.packing_mode = currentPackingMode();
    if (cfg.random_seed != null && cfg.random_seed !== "") input.random_seed = cfg.random_seed;
    if (cfg.time_limit_seconds != null && cfg.time_limit_seconds !== "") {
      input.time_limit_seconds = cfg.time_limit_seconds;
    }
    lastConvertedInput = input;
    $("algorithm-input-json").value = prettyJson(input);

    const d = converted.details || {};
    $("bedbpp-hint").textContent =
      `Pedido ${orderId} · ${d.n_items ?? "?"} ítems · target ${d.target || "?"} → entrada del algoritmo (1 contenedor + ítems).`;
    if (!silent) {
      showAlert(alertBox, `Entrada actualizada para el pedido ${orderId}.`, "ok");
    }
    return input;
  } catch (err) {
    if (seq !== previewSeq) return null;
    clearAlgorithmInputPreview();
    showAlert(alertBox, err.message);
    return null;
  }
}

async function onAlgorithmChange() {
  const name = $("algorithm-select").value;
  const alertBox = $("execute-alert");
  alertBox.innerHTML = "";
  $("result-kpis").innerHTML = "";
  $("result-json").textContent = "{}";
  $("result-layout").innerHTML = '<p class="muted">Ejecuta un algoritmo para ver el layout 2D de la solución.</p>';
  $("result-layout-3d").innerHTML = '<p class="muted">La vista 3D interactiva (Plotly) aparecerá aquí tras ejecutar.</p>';
  $("result-validation").innerHTML = '<p class="muted">Tras ejecutar, aquí verás el cumplimiento de cada restricción solicitada.</p>';
  if (!name) {
    currentDetail = null;
    configPayload = {};
    $("algo-meta").innerHTML = "";
    $("params-form").innerHTML = '<p class="muted">Selecciona un algoritmo para cargar su configuración.</p>';
    await refreshAlgorithmInputPreview({ silent: true });
    return;
  }
  try {
    currentDetail = await API.getAlgorithm(name, currentPackingMode());
    renderAlgorithmMeta(currentDetail);
    const packingMode = currentPackingMode();
    const defaults = { ...(currentDetail.default_parameters || {}) };
    if (packingMode === "online") defaults.sort_strategy = "input_order";
    configPayload = {
      parameters: defaults,
      constraints: {
        non_overlap: true,
        containment: true,
        allow_rotation: true,
        max_weight: true,
        basic_stability: $("problem-type-select").value === "STACKING_AWARE",
        load_bearing: false,
      },
      random_seed: currentDetail.default_parameters?.random_seed ?? null,
      time_limit_seconds: currentDetail.default_parameters?.time_limit_seconds ?? null,
    };
    mountConfigForm();
    await refreshAlgorithmInputPreview({ silent: true });
  } catch (err) {
    showAlert(alertBox, err.message);
  }
}

function onProblemChange(problemType) {
  updateHint(problemType);
  populateAlgorithms(problemType);
  $("algorithm-select").value = "";
  onAlgorithmChange();
}

function onPackingModeChange() {
  const problemType = $("problem-type-select").value;
  populateAlgorithms(problemType);
  const keep = $("algorithm-select").value;
  if (keep && ![...$("algorithm-select").options].some((o) => o.value === keep)) {
    $("algorithm-select").value = "";
  }
  onAlgorithmChange();
}

function syncDatasetFromTextarea() {
  const raw = $("bedbpp-raw").value.trim();
  if (!raw) return;
  BedBpp.ingestRaw(raw);
  const keep = $("bedbpp-order-select").value;
  BedBpp.fillOrderSelect($("bedbpp-order-select"), keep);
}

async function ensureBedBppSample() {
  if (BedBpp.sample) {
    BedBpp.fillOrderSelect($("bedbpp-order-select"), $("bedbpp-order-select").value);
    $("bedbpp-raw").value = prettyJson(BedBpp.sample);
    return;
  }
  await BedBpp.loadSample();
  $("bedbpp-raw").value = prettyJson(BedBpp.sample);
  BedBpp.fillOrderSelect($("bedbpp-order-select"));
  $("bedbpp-hint").textContent =
    `${BedBpp.orderSummaries.length} pedidos cargados. Selecciona uno para ver la entrada del algoritmo.`;
}

function renderExecuteResult(data, inputPayload) {
  const solution = data.solution || {};
  const metrics = solution.metrics || {};
  const valid = solution.validation_report?.is_valid;
  $("result-kpis").innerHTML = `
    <div class="kpi"><span class="muted">Estado</span><strong>${data.status}</strong></div>
    <div class="kpi"><span class="muted">Válido</span><strong>${valid ? "Sí" : "No"}</strong></div>
    <div class="kpi"><span class="muted">Empacados</span><strong>${metrics.items_packed ?? "—"}</strong></div>
    <div class="kpi"><span class="muted">Sin empacar</span><strong>${metrics.items_unpacked ?? "—"}</strong></div>
    <div class="kpi"><span class="muted">Utilización</span><strong>${formatPct(metrics.volume_utilization)}</strong></div>
    <div class="kpi"><span class="muted">Tiempo (s)</span><strong>${metrics.execution_time_seconds?.toFixed?.(3) ?? "—"}</strong></div>`;
  $("result-json").textContent = prettyJson(data);
  ConstraintValidation.render($("result-validation"), inputPayload?.constraints, solution.validation_report, {
    title: "Validación de restricciones solicitadas",
  });
  LayoutViz.render($("result-layout"), {
    solution,
    containers: inputPayload?.containers,
    boxes: inputPayload?.boxes,
    title: "Layout 2D de la solución",
  });
  LayoutViz3D.render($("result-layout-3d"), {
    solution,
    containers: inputPayload?.containers,
    boxes: inputPayload?.boxes,
    title: "Layout 3D interactivo",
  });
}

async function runExecute() {
  const alertBox = $("execute-alert");
  alertBox.innerHTML = "";
  const name = $("algorithm-select").value;
  if (!name) {
    showAlert(alertBox, "Selecciona tipo de problema y algoritmo.");
    return;
  }
  const orderId = $("bedbpp-order-select").value;
  if (!orderId) {
    showAlert(alertBox, "Selecciona un pedido del dataset BED-BPP.");
    return;
  }

  // Asegura que el preview refleje config + pedido actuales.
  let payload;
  try {
    const raw = $("algorithm-input-json").value.trim();
    if (raw) {
      payload = JSON.parse(raw);
    } else {
      payload = await refreshAlgorithmInputPreview({ silent: true });
    }
  } catch {
    showAlert(alertBox, "El JSON de entrada del algoritmo no es válido.");
    return;
  }
  if (!payload || !payload.containers || !payload.items) {
    payload = await refreshAlgorithmInputPreview({ silent: true });
  }
  if (!payload) {
    showAlert(alertBox, "No hay entrada del algoritmo para el pedido seleccionado.");
    return;
  }

  const button = $("run-btn");
  button.disabled = true;
  button.textContent = "Ejecutando…";
  try {
    const result = await API.execute(name, payload);
    lastConvertedInput = payload;
    $("algorithm-input-json").value = prettyJson(payload);
    renderExecuteResult(result, payload);
    showAlert(alertBox, `Ejecución completada (pedido ${orderId}).`, "ok");
  } catch (err) {
    showAlert(alertBox, err.message);
  } finally {
    button.disabled = false;
    button.textContent = "Ejecutar algoritmo";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  setActiveNav("execute");
  initResultTabs();
  const alertBox = $("execute-alert");
  $("params-form").innerHTML = '<p class="muted">Selecciona un algoritmo para cargar su configuración.</p>';
  $("run-btn").addEventListener("click", runExecute);
  $("algorithm-select").addEventListener("change", onAlgorithmChange);
  $("bedbpp-order-select").addEventListener("change", () => refreshAlgorithmInputPreview());
  $("refresh-input-btn").addEventListener("click", () => refreshAlgorithmInputPreview());
  $("bedbpp-load-btn").addEventListener("click", async () => {
    try {
      BedBpp.sample = null;
      await ensureBedBppSample();
      clearAlgorithmInputPreview();
      showAlert(alertBox, "Muestra BED-BPP cargada. Selecciona un pedido.", "ok");
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });
  $("bedbpp-raw").addEventListener("change", async () => {
    try {
      syncDatasetFromTextarea();
      BedBpp.fillOrderSelect($("bedbpp-order-select"), $("bedbpp-order-select").value);
      await refreshAlgorithmInputPreview({ silent: true });
      showAlert(alertBox, "Dataset BED-BPP actualizado.", "ok");
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });
  try {
    implemented = await API.listAlgorithms({ status: "implemented" });
    ProblemContext.mountPackingMode($("packing-mode-select"), onPackingModeChange);
    ProblemContext.mountSelector($("problem-type-select"), {
      bedBppOnly: true,
      onChange: onProblemChange,
    });
    await ensureBedBppSample();
    const params = new URLSearchParams(window.location.search);
    if (params.get("problem_type") && BED_BPP_PROBLEM_TYPES.some((p) => p.id === params.get("problem_type"))) {
      $("problem-type-select").value = params.get("problem_type");
      ProblemContext.setSelected(params.get("problem_type"));
      onProblemChange(params.get("problem_type"));
    }
    const orderId = params.get("order_id");
    if (orderId && [...$("bedbpp-order-select").options].some((o) => o.value === orderId)) {
      $("bedbpp-order-select").value = orderId;
    }
    if (params.get("algorithm")) {
      const wanted = params.get("algorithm");
      if (![...$("algorithm-select").options].some((o) => o.value === wanted)) {
        showAlert(
          alertBox,
          `El algoritmo ${wanted} no está en el modo ${currentPackingMode()}. Cambia a Online si es una política aprendida.`
        );
      } else {
        $("algorithm-select").value = wanted;
        await onAlgorithmChange();
      }
    } else if (orderId) {
      await refreshAlgorithmInputPreview({ silent: true });
    }
  } catch (err) {
    showAlert(alertBox, err.message);
  }
});
