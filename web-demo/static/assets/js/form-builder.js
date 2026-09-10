/** Constructor de formulario UI sincronizado con JSON de entrada. */

const FormBuilder = {
  container: null,
  payload: {},
  parameterHints: {},
  onChange: null,
  mode: "full",

  mount(containerEl, payload, parameterHints = {}, onChange) {
    this.container = containerEl;
    this.payload = JSON.parse(JSON.stringify(payload || {}));
    this.parameterHints = parameterHints || {};
    this.onChange = onChange;
    this.mode = "full";
    this.render();
  },

  /** Solo restricciones + parámetros (entrada geométrica = BED-BPP). */
  mountConfig(containerEl, payload, parameterHints = {}, onChange) {
    this.container = containerEl;
    this.payload = JSON.parse(JSON.stringify(payload || {}));
    this.parameterHints = parameterHints || {};
    this.onChange = onChange;
    this.mode = "config";
    this.render();
  },

  notify() {
    if (this.onChange) this.onChange(this.payload);
  },

  setPayload(payload, parameterHints) {
    this.payload = JSON.parse(JSON.stringify(payload || {}));
    if (parameterHints) this.parameterHints = parameterHints;
    this.render();
  },

  render() {
    const p = this.payload;
    const constraints = p.constraints || {};
    const parameters = p.parameters || {};

    if (this.mode === "config") {
      this.container.innerHTML = `
        <div class="form-grid">
          <section class="form-section">
            <h3>General</h3>
            ${this.field("random_seed", "Semilla aleatoria", p.random_seed ?? "", "number")}
            ${this.field("time_limit_seconds", "Límite de tiempo (s)", p.time_limit_seconds ?? "", "number")}
          </section>
          <section class="form-section">
            <h3>Restricciones</h3>
            <div class="checkbox-grid compact">
              ${this.checkbox("constraints.non_overlap", "No solapamiento", constraints.non_overlap !== false)}
              ${this.checkbox("constraints.containment", "Contención", constraints.containment !== false)}
              ${this.checkbox("constraints.allow_rotation", "Rotación", constraints.allow_rotation !== false)}
              ${this.checkbox("constraints.max_weight", "Peso máximo", constraints.max_weight !== false)}
              ${this.checkbox("constraints.basic_stability", "Estabilidad básica", !!constraints.basic_stability)}
              ${this.checkbox("constraints.load_bearing", "Capacidad de carga", !!constraints.load_bearing)}
            </div>
          </section>
          <section class="form-section full">
            <h3>Parámetros del algoritmo</h3>
            <div id="fb-parameters">${this.renderParameters(parameters)}</div>
            <button type="button" class="secondary small" data-action="add-param">Añadir parámetro</button>
          </section>
        </div>`;
      this.bindEvents();
      return;
    }

    this.container.innerHTML = `
      <div class="form-grid">
        <section class="form-section">
          <h3>General</h3>
          ${this.field("request_id", "Request ID", p.request_id || "")}
          ${p.problem_type ? this.readonly("problem_type", "Tipo de problema", p.problem_type) : ""}
          ${this.field("objective", "Objetivo", p.objective || "")}
          ${this.field("random_seed", "Semilla aleatoria", p.random_seed ?? "", "number")}
          ${this.field("time_limit_seconds", "Límite de tiempo (s)", p.time_limit_seconds ?? "", "number")}
        </section>

        <section class="form-section">
          <h3>Restricciones</h3>
          <div class="checkbox-grid compact">
            ${this.checkbox("constraints.non_overlap", "No solapamiento", constraints.non_overlap !== false)}
            ${this.checkbox("constraints.containment", "Contención", constraints.containment !== false)}
            ${this.checkbox("constraints.allow_rotation", "Rotación", constraints.allow_rotation !== false)}
            ${this.checkbox("constraints.max_weight", "Peso máximo", constraints.max_weight !== false)}
            ${this.checkbox("constraints.basic_stability", "Estabilidad básica", !!constraints.basic_stability)}
            ${this.checkbox("constraints.load_bearing", "Capacidad de carga", !!constraints.load_bearing)}
          </div>
        </section>

        <section class="form-section">
          <h3>Parámetros del algoritmo</h3>
          <div id="fb-parameters">${this.renderParameters(parameters)}</div>
          <button type="button" class="secondary small" data-action="add-param">Añadir parámetro</button>
        </section>

        ${p.problem_type !== "CARTONIZATION" ? `
        <section class="form-section full">
          <h3>Contenedores</h3>
          ${this.renderContainers(p.containers || [])}
        </section>` : ""}

        <section class="form-section full">
          <h3>Ítems</h3>
          ${this.renderItems(p.items || [])}
        </section>

        ${p.problem_type === "CARTONIZATION" || (p.boxes && p.boxes.length) ? `
        <section class="form-section full">
          <h3>Cajas (cartonization)</h3>
          ${this.renderBoxes(p.boxes || [])}
        </section>` : ""}
      </div>`;

    this.bindEvents();
  },

  field(path, label, value, type = "text") {
    return `<label class="form-field"><span>${label}</span>
      <input data-path="${path}" type="${type}" value="${this.escape(value)}"></label>`;
  },

  readonly(path, label, value) {
    return `<label class="form-field"><span>${label}</span>
      <input data-path="${path}" type="text" value="${this.escape(value)}" readonly></label>`;
  },

  checkbox(path, label, checked) {
    return `<label><input type="checkbox" data-path="${path}" ${checked ? "checked" : ""}> ${label}</label>`;
  },

  escape(value) {
    return String(value ?? "").replace(/"/g, "&quot;");
  },

  renderParameters(parameters) {
    const keys = Object.keys(parameters);
    if (!keys.length) return '<p class="muted">Sin parámetros. Añade clave/valor si el algoritmo los requiere.</p>';
    return keys
      .map((key) => {
        const hint = this.parameterHints[key] ? `<span class="muted" style="font-size:0.85em">${this.escape(this.parameterHints[key])}</span>` : "";
        return `
        <div class="param-row" style="flex-wrap:wrap">
          <input data-param-key="${this.escape(key)}" value="${this.escape(key)}" placeholder="clave">
          <input data-param-val-key="${this.escape(key)}" value="${this.escape(parameters[key])}" placeholder="valor">
          <button type="button" class="secondary small" data-remove-param="${this.escape(key)}">✕</button>
          ${hint}
        </div>`;
      })
      .join("");
  },

  renderContainers(containers) {
    return `${this.entityTable(
      "container",
      ["id", "length", "width", "height", "max_weight"],
      containers
    )}<button type="button" class="secondary small" data-action="add-container">Añadir contenedor</button>`;
  },

  renderItems(items) {
    return `${this.entityTable(
      "item",
      ["id", "length", "width", "height", "weight", "quantity", "max_load_on_top"],
      items
    )}<button type="button" class="secondary small" data-action="add-item">Añadir ítem</button>`;
  },

  renderBoxes(boxes) {
    return `${this.entityTable(
      "box",
      ["id", "length", "width", "height", "max_weight"],
      boxes
    )}<button type="button" class="secondary small" data-action="add-box">Añadir caja</button>`;
  },

  entityTable(kind, columns, rows) {
    const header = columns.map((c) => `<th>${c}</th>`).join("") + "<th></th>";
    const body = (rows || [])
      .map(
        (row, idx) => `
        <tr data-entity="${kind}" data-index="${idx}">
          ${columns
            .map(
              (col) =>
                `<td><input data-entity-field="${col}" value="${this.escape(row[col] ?? "")}"></td>`
            )
            .join("")}
          <td><button type="button" class="secondary small" data-remove-entity="${kind}" data-index="${idx}">✕</button></td>
        </tr>`
      )
      .join("");
    return `<div class="table-wrap entity-table"><table><thead><tr>${header}</tr></thead><tbody>${body || ""}</tbody></table></div>`;
  },

  bindEvents() {
    this.container.querySelectorAll("input[data-path]").forEach((input) => {
      input.addEventListener("input", () => this.applyScalar(input));
      input.addEventListener("change", () => this.applyScalar(input));
    });
    this.container.querySelectorAll("input[type=checkbox][data-path]").forEach((input) => {
      input.addEventListener("change", () => this.applyCheckbox(input));
    });
    this.container.querySelectorAll("tr[data-entity] input").forEach((input) => {
      input.addEventListener("input", () => this.applyEntityTables());
    });
    this.container.querySelectorAll("[data-remove-entity]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const kind = btn.dataset.removeEntity;
        const idx = Number(btn.dataset.index);
        const key = kind === "container" ? "containers" : kind === "box" ? "boxes" : "items";
        this.payload[key].splice(idx, 1);
        this.render();
        this.notify();
      });
    });
    this.container.querySelectorAll("[data-action=add-container]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.payload.containers = this.payload.containers || [];
        this.payload.containers.push({ id: `C${this.payload.containers.length + 1}`, length: 100, width: 80, height: 80, max_weight: 500 });
        this.render();
        this.notify();
      });
    });
    this.container.querySelectorAll("[data-action=add-item]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.payload.items = this.payload.items || [];
        this.payload.items.push({ id: `I${this.payload.items.length + 1}`, length: 30, width: 25, height: 20, weight: 5, quantity: 1 });
        this.render();
        this.notify();
      });
    });
    this.container.querySelectorAll("[data-action=add-box]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.payload.boxes = this.payload.boxes || [];
        this.payload.boxes.push({ id: `BOX_${this.payload.boxes.length + 1}`, length: 40, width: 30, height: 25, max_weight: 20 });
        this.render();
        this.notify();
      });
    });
    this.container.querySelectorAll("[data-param-key]").forEach((input) => {
      input.addEventListener("input", () => this.applyParameters());
    });
    this.container.querySelectorAll("[data-param-val-key]").forEach((input) => {
      input.addEventListener("input", () => this.applyParameters());
    });
    this.container.querySelectorAll("[data-remove-param]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.dataset.removeParam;
        delete this.payload.parameters[key];
        this.render();
        this.notify();
      });
    });
    this.container.querySelectorAll("[data-action=add-param]").forEach((btn) => {
      btn.addEventListener("click", () => {
        this.payload.parameters = this.payload.parameters || {};
        const newKey = `param_${Object.keys(this.payload.parameters).length + 1}`;
        this.payload.parameters[newKey] = "";
        this.render();
        this.notify();
      });
    });
  },

  applyScalar(input) {
    const path = input.dataset.path;
    let value = input.value;
    if (input.type === "number" && value !== "") value = Number(value);
    if (path === "random_seed" || path === "time_limit_seconds") {
      this.payload[path] = value === "" ? null : value;
    } else {
      this.setPath(path, value);
    }
    this.notify();
  },

  applyCheckbox(input) {
    this.setPath(input.dataset.path, input.checked);
    this.notify();
  },

  applyParameters() {
    const next = {};
    this.container.querySelectorAll(".param-row").forEach((row) => {
      const keyInput = row.querySelector("[data-param-key]");
      const valInput = row.querySelector("[data-param-val-key]");
      const key = keyInput.value.trim();
      if (!key) return;
      let val = valInput.value;
      if (val === "true") val = true;
      else if (val === "false") val = false;
      else if (val !== "" && !Number.isNaN(Number(val)) && val.trim() !== "") val = Number(val);
      next[key] = val;
    });
    this.payload.parameters = next;
    this.notify();
  },

  applyEntityTables() {
    ["container", "item", "box"].forEach((kind) => {
      const key = kind === "container" ? "containers" : kind === "box" ? "boxes" : "items";
      const rows = [];
      this.container.querySelectorAll(`tr[data-entity="${kind}"]`).forEach((tr) => {
        const row = {};
        tr.querySelectorAll("[data-entity-field]").forEach((input) => {
          const field = input.dataset.entityField;
          let val = input.value;
          if (["length", "width", "height", "weight", "max_weight", "quantity", "max_load_on_top"].includes(field)) {
            val = val === "" ? undefined : Number(val);
          }
          if (val !== undefined && val !== "") row[field] = val;
        });
        rows.push(row);
      });
      if (rows.length) this.payload[key] = rows;
    });
    this.notify();
  },

  setPath(path, value) {
    const parts = path.split(".");
    let ref = this.payload;
    for (let i = 0; i < parts.length - 1; i += 1) {
      const part = parts[i];
      ref[part] = ref[part] || {};
      ref = ref[part];
    }
    ref[parts[parts.length - 1]] = value;
  },
};
