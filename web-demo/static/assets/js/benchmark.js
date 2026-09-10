let implemented = [];
let profiles = [];

function updateHint(problemType) {
  const meta = ProblemContext.meta(problemType);
  const orderId = $("bedbpp-order-select")?.value;
  const extra = orderId ? `Pedido seleccionado: ${orderId}.` : "Selecciona un pedido del dataset.";
  $("instance-hint").innerHTML = meta
    ? `<strong>${meta.label}</strong> — ${meta.hint} ${extra}`
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
      // parameters vacíos: el backend rellena defaults seguros por algoritmo.
      const checked = idx < 3 ? "checked" : "";
      return `
      <label>
        <input class="engine-check" type="checkbox" value="${algo.name}" data-parameters='{}' ${checked}>
        <span><strong>${algo.display_name}</strong><br><span class="muted">${algo.name}</span></span>
      </label>`;
    })
    .join("");
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
  LayoutViz3D.renderCompare($("benchmark-layout-3d"), result.results, inputPayload?.containers, inputPayload?.boxes);
}

function renderBenchmarkValidation(result, inputPayload) {
  ConstraintValidation.renderBenchmarkSummary(
    $("benchmark-validation"),
    result.results,
    inputPayload?.constraints
  );
}

function syncDatasetFromTextarea() {
  const raw = $("bedbpp-raw").value.trim();
  if (!raw) return;
  BedBpp.ingestRaw(raw);
  const keep = $("bedbpp-order-select").value;
  BedBpp.fillOrderSelect($("bedbpp-order-select"), keep);
  $("bedbpp-hint").textContent = `${BedBpp.orderSummaries.length} pedidos en el dataset.`;
  updateHint($("problem-type-select").value);
}

async function ensureBedBppSample() {
  if (BedBpp.sample) {
    BedBpp.fillOrderSelect($("bedbpp-order-select"), $("bedbpp-order-select").value);
    return;
  }
  await BedBpp.loadSample();
  $("bedbpp-raw").value = prettyJson(BedBpp.sample);
  BedBpp.fillOrderSelect($("bedbpp-order-select"));
  $("bedbpp-hint").textContent = `${BedBpp.orderSummaries.length} pedidos en la muestra BED-BPP.`;
  updateHint($("problem-type-select").value);
}

async function onProblemChange(problemType) {
  const alertBox = $("benchmark-alert");
  alertBox.innerHTML = "";
  $("benchmark-layout").innerHTML = '<p class="muted">Ejecuta un benchmark para comparar layouts mejor vs peor.</p>';
  $("benchmark-layout-3d").innerHTML = '<p class="muted">Vista 3D (Plotly) del mejor vs peor tras el benchmark.</p>';
  $("benchmark-validation").innerHTML =
    '<p class="muted">Ejecuta un benchmark para ver el cumplimiento de restricciones de cada algoritmo.</p>';
  $("profile-select").value = "";
  try {
    await refreshProfiles(problemType);
    renderEngineChoices(problemType);
    updateHint(problemType);
  } catch (err) {
    showAlert(alertBox, err.message);
  }
}

async function runBenchmark() {
  const alertBox = $("benchmark-alert");
  alertBox.innerHTML = "";
  try {
    syncDatasetFromTextarea();
  } catch (err) {
    showAlert(alertBox, err.message);
    return;
  }
  if (!BedBpp.sample) {
    try {
      await ensureBedBppSample();
    } catch (err) {
      showAlert(alertBox, err.message);
      return;
    }
  }
  const orderId = $("bedbpp-order-select").value;
  if (!orderId) {
    showAlert(alertBox, "Selecciona un pedido del dataset BED-BPP.");
    return;
  }
  const problemType = $("problem-type-select").value;
  const profile = $("profile-select").value;
  const engines = selectedEngines();
  if (!profile && engines.length < 2) {
    showAlert(alertBox, "Selecciona ≥2 algoritmos o un perfil predefinido.");
    return;
  }

  const wrapper = BedBpp.buildWrapper({
    orderId,
    problemType,
    profile: profile || undefined,
    engines: profile ? undefined : engines,
  });

  const button = $("benchmark-btn");
  button.disabled = true;
  button.textContent = "Ejecutando…";
  $("benchmark-layout").innerHTML = '<p class="muted">Generando visualizaciones…</p>';
  try {
    const [result, converted] = await Promise.all([
      API.benchmark(wrapper),
      BedBpp.convert({
        orderId,
        problemType,
        mode: "benchmark",
        profile: profile || undefined,
        engines: profile ? undefined : engines,
      }),
    ]);
    renderBenchmarkTable(result);
    $("benchmark-json-out").textContent = prettyJson(result);
    renderBenchmarkValidation(result, converted.input);
    renderBenchmarkLayout(result, converted.input);
    showAlert(alertBox, `Benchmark completado (${result.results.length} motores) · pedido ${orderId}.`, "ok");
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
  $("bedbpp-load-btn").addEventListener("click", async () => {
    try {
      BedBpp.sample = null;
      await ensureBedBppSample();
      showAlert($("benchmark-alert"), "Muestra BED-BPP cargada.", "ok");
    } catch (err) {
      showAlert($("benchmark-alert"), err.message);
    }
  });
  $("bedbpp-order-select").addEventListener("change", () => updateHint($("problem-type-select").value));
  $("bedbpp-raw").addEventListener("change", () => {
    try {
      syncDatasetFromTextarea();
      showAlert($("benchmark-alert"), "Dataset BED-BPP actualizado.", "ok");
    } catch (err) {
      showAlert($("benchmark-alert"), err.message);
    }
  });
  $("profile-select").addEventListener("change", () => {
    if ($("profile-select").value) {
      document.querySelectorAll(".engine-check").forEach((el) => {
        el.checked = false;
      });
    }
  });
  try {
    implemented = await API.listAlgorithms({ status: "implemented" });
    ProblemContext.mountSelector($("problem-type-select"), {
      bedBppOnly: true,
      onChange: onProblemChange,
    });
    ensureBedBppSample().catch(() => {});
  } catch (err) {
    showAlert($("benchmark-alert"), err.message);
  }
});
