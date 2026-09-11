const API = {
  async request(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = { raw: text };
      }
    }
    if (!response.ok) {
      const message =
        data?.error?.message ||
        data?.detail ||
        (typeof data?.raw === "string" ? data.raw : null) ||
        `HTTP ${response.status}`;
      throw new Error(message);
    }
    return data;
  },

  health() {
    return this.request("/demo/health");
  },

  metadata() {
    return this.request("/api/v1/metadata");
  },

  listAlgorithms(params = {}) {
    const query = new URLSearchParams(params).toString();
    return this.request(`/api/v1/algorithms${query ? `?${query}` : ""}`);
  },

  getAlgorithm(name, packingMode) {
    const query = packingMode ? `?packing_mode=${encodeURIComponent(packingMode)}` : "";
    return this.request(`/api/v1/algorithms/${encodeURIComponent(name)}${query}`);
  },

  inputExample(name, problemType) {
    const query = problemType ? `?problem_type=${encodeURIComponent(problemType)}` : "";
    return this.request(`/api/v1/algorithms/${encodeURIComponent(name)}/input-example${query}`);
  },

  execute(name, payload) {
    return this.request(`/api/v1/algorithms/${encodeURIComponent(name)}/execute`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  benchmark(payload) {
    return this.request("/api/v1/benchmark", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  benchmarkProfiles(problemType) {
    const query = problemType ? `?problem_type=${encodeURIComponent(problemType)}` : "";
    return this.request(`/api/v1/benchmark/profiles${query}`);
  },
};

function $(id) {
  return document.getElementById(id);
}

function setActiveNav(page) {
  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.page === page);
  });
}

function showAlert(container, message, type = "error") {
  container.innerHTML = `<div class="alert ${type}">${message}</div>`;
}

function formatPct(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function prettyJson(value) {
  return JSON.stringify(value, null, 2);
}

async function loadServiceSummary(targetId) {
  const target = $(targetId);
  if (!target) return;
  try {
    const [health, metadata] = await Promise.all([API.health(), API.metadata()]);
    const count = metadata.implemented_algorithms?.length ?? 0;
    target.innerHTML = `
      <div class="grid">
        <div class="card">
          <h3>Estado del sistema</h3>
          <span class="badge ${health.api_reachable ? "ok" : "warn"}">
            ${health.api_reachable ? "API operativa" : "API no disponible"}
          </span>
          <p class="muted">Versión ${metadata.service_version || health.api?.service_version || "—"}</p>
          <p class="muted">${metadata.description || ""}</p>
        </div>
        <div class="card">
          <h3>Algoritmos implementados</h3>
          <strong style="font-size:1.5rem">${count}</strong>
          <p class="muted">Listos para ejecutar vía catálogo</p>
        </div>
        <div class="card">
          <h3>Modo simulación</h3>
          <p class="muted">Sin contratos, políticas ni soberanía de datos. Solo funcionalidad.</p>
        </div>
      </div>`;
  } catch (err) {
    showAlert(target, `No se pudo conectar con los servicios: ${err.message}`);
  }
}
