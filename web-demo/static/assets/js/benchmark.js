let implemented = [];
let profiles = [];
let showcaseDescription = "";

function updateHint(problemType) {
  const meta = ProblemContext.meta(problemType);
  $("instance-hint").innerHTML = meta
    ? `<strong>${meta.label}</strong> — ${showcaseDescription || meta.hint}`
    : "";
}

function selectedEngines() {
  return [...document.querySelectorAll(".engine-check:checked")].map((el) => ({
    name: el.value,
    parameters: JSON.parse(el.dataset.parameters || "{}"),
  }));
}

function renderEngineChoices(problemType) {
  const grid = $("engine-grid");
  const compatible = ProblemContext.filterAlgorithms(implemented, problemType);
  if (!compatible.length) {
    grid.innerHTML = '<p class="muted">No hay algoritmos implementados para este tipo.</p>';
    return;
  }
  grid.innerHTML = compatible
    .map((algo, idx) => {
      const params = algo.name.includes("metaheuristic")
        ? { base_algorithm: "best_fit_decreasing_3d", iterations: 15, random_seed: 42 }
        : algo.algorithm_family === "cartonization" || algo.name.includes("box")
          ? { sort_strategy: "volume_desc" }
          : { sort_strategy: "volume_desc" };
      const checked = idx < 3 ? "checked" : "";
      return `
      <label>
        <input class="engine-check" type="checkbox" value="${algo.name}" data-parameters='${JSON.stringify(params)}' ${checked}>
        <span><strong>${algo.display_name}</strong><br><span class="muted">${algo.name}</span></span>
      </label>`;
    })
    .join("");
}

async function loadShowcaseInstance(problemType) {
  const { payload, description } = await ProblemContext.loadShowcase(problemType);
  showcaseDescription = description || "";
  const bench = ProblemContext.benchmarkPayloadFromShowcase(payload, problemType);
  $("benchmark-json").value = prettyJson(bench);
  updateHint(problemType);
}

async function refreshProfiles(problemType) {
  const data = await API.benchmarkProfiles(problemType);
  profiles = data.profiles || [];
  $("profile-select").innerHTML =
    `<option value="">Selección manual de algoritmos</option>` +
    profiles
      .filter((p) => p.problem_type === problemType)
      .map((p) => `<option value="${p.profile}">${p.profile} (${p.engines_count} motores)</option>`)
      .join("");
}

function renderBenchmarkTable(data) {
  const best = data.ranking?.[0];
  $("ranking-box").innerHTML = `
    <strong>Ranking:</strong> ${(data.ranking || []).join(" → ")}<br>
    <span class="muted">${data.ranking_explanation || ""}</span>`;

  const metricKeys = [
    ["items_packed", "Empacados"],
    ["items_unpacked", "Sin empacar"],
    ["volume_utilization", "Utilización", true],
    ["containers_used", "Contenedores"],
    ["execution_time_seconds", "Tiempo (s)"],
    ["constraint_violations", "Violaciones"],
  ];

  const header = metricKeys.map(([, label]) => `<th>${label}</th>`).join("");
  const rows = data.results
    .map((r) => {
      const m = r.metrics || {};
      const isBest = r.engine === best;
      const cells = metricKeys
        .map(([key, , isPct]) => {
          const val = m[key];
          const display = isPct ? formatPct(val) : val ?? "—";
          return `<td>${display}</td>`;
        })
        .join("");
      return `<tr class="${isBest ? "best" : ""}">
        <td><code>${r.engine}</code>${isBest ? ' <span class="rank">#1</span>' : ""}</td>
        <td>${r.is_valid ? "✓" : "✗"}</td>
        ${cells}
      </tr>`;
    })
    .join("");

  $("benchmark-table").innerHTML = `
    <div class="table-wrap"><table>
      <thead><tr><th>Motor</th><th>Válido</th>${header}</tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

function renderBenchmarkLayout(result, inputPayload) {
  LayoutViz.renderCompare($("benchmark-layout"), result.results, inputPayload?.containers, inputPayload?.boxes);
}

function renderBenchmarkValidation(result, inputPayload) {
  ConstraintValidation.renderBenchmarkSummary(
    $("benchmark-validation"),
    result.results,
    inputPayload?.constraints
  );
}

async function onProblemChange(problemType) {
  const alertBox = $("benchmark-alert");
  alertBox.innerHTML = "";
  $("benchmark-layout").innerHTML = '<p class="muted">Ejecuta un benchmark para comparar layouts mejor vs peor.</p>';
  $("benchmark-validation").innerHTML =
    '<p class="muted">Ejecuta un benchmark para ver el cumplimiento de restricciones de cada algoritmo.</p>';
  $("profile-select").value = "";
  try {
    await Promise.all([refreshProfiles(problemType), loadShowcaseInstance(problemType)]);
    renderEngineChoices(problemType);
  } catch (err) {
    showAlert(alertBox, err.message);
  }
}

async function runBenchmark() {
  const alertBox = $("benchmark-alert");
  alertBox.innerHTML = "";
  let payload;
  try {
    payload = JSON.parse($("benchmark-json").value);
  } catch {
    showAlert(alertBox, "JSON de instancia inválido.");
    return;
  }
  const profile = $("profile-select").value;
  const engines = selectedEngines();
  if (profile) {
    payload.profile = profile;
    delete payload.engines;
  } else if (engines.length >= 2) {
    payload.engines = engines;
    delete payload.profile;
  } else {
    showAlert(alertBox, "Selecciona ≥2 algoritmos o un perfil predefinido.");
    return;
  }
  payload.problem_type = $("problem-type-select").value;
  const button = $("benchmark-btn");
  button.disabled = true;
  button.textContent = "Ejecutando…";
  $("benchmark-layout").innerHTML = '<p class="muted">Generando visualizaciones…</p>';
  try {
    const result = await API.benchmark(payload);
    renderBenchmarkTable(result);
    $("benchmark-json-out").textContent = prettyJson(result);
    renderBenchmarkValidation(result, payload);
    renderBenchmarkLayout(result, payload);
    showAlert(alertBox, `Benchmark completado (${result.results.length} motores).`, "ok");
  } catch (err) {
    showAlert(alertBox, err.message);
  } finally {
    button.disabled = false;
    button.textContent = "Ejecutar benchmark";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  setActiveNav("benchmark");
  $("benchmark-btn").addEventListener("click", runBenchmark);
  $("load-showcase-btn").addEventListener("click", () => onProblemChange($("problem-type-select").value));
  $("profile-select").addEventListener("change", () => {
    if ($("profile-select").value) {
      document.querySelectorAll(".engine-check").forEach((el) => {
        el.checked = false;
      });
    }
  });
  try {
    implemented = await API.listAlgorithms({ status: "implemented" });
    ProblemContext.mountSelector($("problem-type-select"), { onChange: onProblemChange });
  } catch (err) {
    showAlert($("benchmark-alert"), err.message);
  }
});
