let implemented = [];
let currentDetail = null;
let currentPayload = {};
let syncing = false;
let jsonListenerAttached = false;

function attachJsonListener() {
  if (jsonListenerAttached) return;
  $("input-json").addEventListener("input", () => {
    if (syncing) return;
    syncing = true;
    syncFormFromJson();
    syncing = false;
  });
  jsonListenerAttached = true;
}

function initTabs() {
  document.querySelectorAll(".tabs:not(.result-tabs) .tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const section = btn.closest("section");
      section.querySelectorAll(".tabs:not(.result-tabs) .tab-btn").forEach((b) => b.classList.remove("active"));
      section.querySelectorAll(".tab-panel").forEach((p) => {
        if (!p.id.startsWith("result-tab-")) p.classList.remove("active");
      });
      btn.classList.add("active");
      $(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });
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

function populateAlgorithms(problemType) {
  const select = $("algorithm-select");
  const compatible = ProblemContext.filterAlgorithms(implemented, problemType);
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

function syncJsonFromForm() {
  $("input-json").value = prettyJson(currentPayload);
}

function syncFormFromJson() {
  try {
    currentPayload = JSON.parse($("input-json").value);
    FormBuilder.setPayload(currentPayload, currentDetail?.parameters || {});
  } catch {
    showAlert($("execute-alert"), "JSON inválido; no se actualizó el formulario.");
  }
}

async function onAlgorithmChange() {
  const name = $("algorithm-select").value;
  const problemType = $("problem-type-select").value;
  const alertBox = $("execute-alert");
  alertBox.innerHTML = "";
  $("result-kpis").innerHTML = "";
  $("result-json").textContent = "{}";
  $("result-layout").innerHTML = '<p class="muted">Ejecuta un algoritmo para ver el layout 2D de la solución.</p>';
  $("result-validation").innerHTML = '<p class="muted">Tras ejecutar, aquí verás el cumplimiento de cada restricción solicitada.</p>';
  if (!name) {
    currentDetail = null;
    currentPayload = {};
    $("algo-meta").innerHTML = "";
    $("input-json").value = "";
    $("input-form").innerHTML = "";
    return;
  }
  try {
    currentDetail = await API.getAlgorithm(name);
    renderAlgorithmMeta(currentDetail);
    currentPayload = await API.inputExample(name, problemType);
    $("input-json").value = prettyJson(currentPayload);
    FormBuilder.mount($("input-form"), currentPayload, currentDetail.parameters || {}, (payload) => {
      if (syncing) return;
      currentPayload = payload;
      syncJsonFromForm();
    });
    attachJsonListener();
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
    title: "Layout de la solución",
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
  FormBuilder.applyEntityTables();
  FormBuilder.applyParameters();
  syncJsonFromForm();
  let payload;
  try {
    payload = JSON.parse($("input-json").value);
  } catch {
    showAlert(alertBox, "El JSON de entrada no es válido.");
    return;
  }
  const button = $("run-btn");
  button.disabled = true;
  button.textContent = "Ejecutando…";
  try {
    const result = await API.execute(name, payload);
    renderExecuteResult(result, payload);
    showAlert(alertBox, "Ejecución completada.", "ok");
  } catch (err) {
    showAlert(alertBox, err.message);
  } finally {
    button.disabled = false;
    button.textContent = "Ejecutar algoritmo";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  setActiveNav("execute");
  initTabs();
  const alertBox = $("execute-alert");
  $("format-btn").addEventListener("click", () => {
    try {
      $("input-json").value = prettyJson(JSON.parse($("input-json").value));
      syncFormFromJson();
    } catch {
      showAlert(alertBox, "JSON inválido.");
    }
  });
  $("run-btn").addEventListener("click", runExecute);
  $("algorithm-select").addEventListener("change", onAlgorithmChange);
  try {
    implemented = await API.listAlgorithms({ status: "implemented" });
    ProblemContext.mountSelector($("problem-type-select"), {
      onChange: onProblemChange,
    });
    const params = new URLSearchParams(window.location.search);
    if (params.get("problem_type")) {
      $("problem-type-select").value = params.get("problem_type");
      ProblemContext.setSelected(params.get("problem_type"));
      onProblemChange(params.get("problem_type"));
    }
    if (params.get("algorithm")) {
      $("algorithm-select").value = params.get("algorithm");
      await onAlgorithmChange();
    }
  } catch (err) {
    showAlert(alertBox, err.message);
  }
});
