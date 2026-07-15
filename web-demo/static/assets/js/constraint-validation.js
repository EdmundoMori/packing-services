/** Análisis y presentación de validación por restricción solicitada. */

const ConstraintValidation = {
  RULES: [
    {
      key: "non_overlap",
      label: "No solapamiento",
      violationTypes: ["OVERLAP"],
      defaultOn: true,
    },
    {
      key: "containment",
      label: "Contención",
      violationTypes: ["CONTAINMENT"],
      defaultOn: true,
    },
    {
      key: "allow_rotation",
      label: "Orientación / rotación",
      violationTypes: ["INVALID_ORIENTATION"],
      defaultOn: true,
      alwaysValidate: true,
    },
    {
      key: "max_weight",
      label: "Peso máximo",
      violationTypes: ["MAX_WEIGHT"],
      defaultOn: true,
    },
    {
      key: "basic_stability",
      label: "Estabilidad básica",
      violationTypes: ["SUPPORT_SURFACE"],
      defaultOn: false,
      warningsAffectValidity: false,
    },
    {
      key: "load_bearing",
      label: "Capacidad de carga",
      violationTypes: ["LOAD_BEARING"],
      defaultOn: false,
    },
  ],

  INTEGRITY_TYPES: [
    "DUPLICATE_ITEM",
    "UNKNOWN_ITEM",
    "UNKNOWN_CONTAINER",
    "UNPACKED_MISMATCH",
  ],

  normalizeConstraints(constraints = {}) {
    return {
      non_overlap: constraints.non_overlap !== false,
      containment: constraints.containment !== false,
      allow_rotation: constraints.allow_rotation !== false,
      max_weight: constraints.max_weight !== false,
      basic_stability: !!constraints.basic_stability,
      load_bearing: !!constraints.load_bearing,
    };
  },

  isRequested(rule, constraints) {
    if (rule.alwaysValidate) return true;
    return !!constraints[rule.key];
  },

  violationsForRule(rule, violations) {
    return (violations || []).filter((v) => rule.violationTypes.includes(v.type));
  },

  statusFromViolations(rule, related) {
    const errors = related.filter((v) => v.severity !== "warning");
    const warnings = related.filter((v) => v.severity === "warning");
    if (errors.length) return { status: "fail", errors, warnings };
    if (warnings.length && rule.warningsAffectValidity !== false) {
      return { status: "warn", errors, warnings };
    }
    if (warnings.length) return { status: "warn", errors, warnings };
    return { status: "pass", errors, warnings };
  },

  analyze(constraints, validationReport) {
    const normalized = this.normalizeConstraints(constraints);
    const violations = validationReport?.violations || [];
    const rules = this.RULES.map((rule) => {
      const requested = this.isRequested(rule, normalized);
      if (!requested) {
        return { ...rule, requested: false, status: "skipped", related: [], errors: [], warnings: [] };
      }
      const related = this.violationsForRule(rule, violations);
      const outcome = this.statusFromViolations(rule, related);
      return { ...rule, requested: true, related, ...outcome };
    });

    const integrityViolations = violations.filter((v) => this.INTEGRITY_TYPES.includes(v.type));
    const integrityErrors = integrityViolations.filter((v) => v.severity !== "warning");
    const integrityStatus = integrityErrors.length ? "fail" : "pass";

    const requestedRules = rules.filter((r) => r.requested);
    const allPass = requestedRules.every((r) => r.status === "pass" || r.status === "warn");
    const hasFail = requestedRules.some((r) => r.status === "fail") || integrityStatus === "fail";

    return {
      constraints: normalized,
      rules,
      integrity: {
        status: integrityStatus,
        violations: integrityViolations,
      },
      summary: {
        requestedCount: requestedRules.length,
        passCount: requestedRules.filter((r) => r.status === "pass").length,
        warnCount: requestedRules.filter((r) => r.status === "warn").length,
        failCount: requestedRules.filter((r) => r.status === "fail").length,
        allRequestedPass: allPass && integrityStatus === "pass",
        hasFail,
      },
      report: validationReport,
    };
  },

  statusBadge(status) {
    const map = {
      pass: { cls: "ok", text: "Cumple" },
      warn: { cls: "warn", text: "Advertencia" },
      fail: { cls: "error", text: "Incumple" },
      skipped: { cls: "muted", text: "No solicitada" },
    };
    const item = map[status] || map.skipped;
    return `<span class="badge ${item.cls}">${item.text}</span>`;
  },

  renderViolationsList(violations) {
    if (!violations.length) return "";
    return `<ul class="validation-violations">
      ${violations
        .map(
          (v) =>
            `<li><code>${v.type}</code> ${v.severity === "warning" ? "(aviso) " : ""}${v.message}</li>`
        )
        .join("")}
    </ul>`;
  },

  render(targetEl, constraints, validationReport, { title, compact = false } = {}) {
    if (!targetEl) return null;
    if (!validationReport) {
      targetEl.innerHTML =
        '<p class="muted">No se recibió informe de validación en la respuesta.</p>';
      return null;
    }

    const analysis = this.analyze(constraints, validationReport);
    const overallValid = validationReport.is_valid && analysis.summary.allRequestedPass;

    if (compact) {
      targetEl.innerHTML = this.statusBadge(overallValid ? "pass" : "fail").replace(
        "Cumple",
        overallValid ? "Válida" : "Inválida"
      );
      return analysis;
    }

    const rows = analysis.rules
      .map((rule) => {
        const detail =
          rule.status === "skipped"
            ? '<span class="muted">Restricción desactivada en la entrada.</span>'
            : this.renderViolationsList(rule.related) ||
              '<span class="muted">Sin violaciones detectadas.</span>';
        return `<tr class="validation-row status-${rule.status}">
          <td><strong>${rule.label}</strong><br><code class="muted">${rule.key}</code></td>
          <td>${rule.requested ? "Sí" : "No"}</td>
          <td>${this.statusBadge(rule.status)}</td>
          <td>${detail}</td>
        </tr>`;
      })
      .join("");

    const integrityDetail =
      this.renderViolationsList(analysis.integrity.violations) ||
      '<span class="muted">Referencias, duplicados y coherencia de no empacados correctos.</span>';

    targetEl.innerHTML = `
      <div class="validation-header">
        <h3>${title || "Validación de restricciones"}</h3>
        <div class="validation-overall">
          ${overallValid
            ? '<span class="badge ok">Solución válida</span>'
            : '<span class="badge error">Solución inválida</span>'}
          <span class="muted">
            ${analysis.summary.passCount} cumplen ·
            ${analysis.summary.warnCount} advertencias ·
            ${analysis.summary.failCount} incumplen ·
            ${this.RULES.length - analysis.summary.requestedCount} no solicitadas
          </span>
        </div>
        <p class="muted">
          Se validan solo las restricciones activas en la entrada del usuario.
          El validador geométrico se ejecuta automáticamente tras cada algoritmo.
        </p>
      </div>
      <div class="table-wrap">
        <table class="validation-table">
          <thead>
            <tr>
              <th>Restricción</th>
              <th>Solicitada</th>
              <th>Estado</th>
              <th>Detalle</th>
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="validation-integrity">
        <h4>Integridad de la solución</h4>
        <p>${this.statusBadge(analysis.integrity.status)} ${integrityDetail}</p>
      </div>`;

    return analysis;
  },

  renderBenchmarkSummary(targetEl, results, constraints) {
    if (!targetEl) return;
    if (!results?.length) {
      targetEl.innerHTML = '<p class="muted">Sin resultados de benchmark.</p>';
      return;
    }

    const rows = results
      .map((r) => {
        const report = r.solution?.validation_report;
        const analysis = report ? this.analyze(constraints, report) : null;
        const valid = analysis?.summary.allRequestedPass && report?.is_valid;
        const cells = this.RULES.map((rule) => {
          if (!analysis) return '<td>—</td>';
          const item = analysis.rules.find((x) => x.key === rule.key);
          if (!item?.requested) return '<td class="muted">—</td>';
          const icon =
            item.status === "pass" ? "✓" : item.status === "warn" ? "!" : item.status === "fail" ? "✗" : "—";
          const cls =
            item.status === "pass" ? "ok" : item.status === "warn" ? "warn" : item.status === "fail" ? "error" : "";
          return `<td class="constraint-cell ${cls}" title="${rule.label}">${icon}</td>`;
        }).join("");

        return `<tr>
          <td><code>${r.engine}</code></td>
          <td>${valid ? '<span class="badge ok">Válida</span>' : '<span class="badge error">Inválida</span>'}</td>
          <td>${r.metrics?.constraint_violations ?? 0}</td>
          ${cells}
        </tr>`;
      })
      .join("");

    const headers = this.RULES.map(
      (r) => `<th title="${r.label}" class="constraint-head">${r.label.split(" ")[0]}</th>`
    ).join("");

    targetEl.innerHTML = `
      <p class="muted">Cada columna indica si el motor cumple la restricción solicitada en la instancia (✓ cumple, ! advertencia, ✗ incumple, — no solicitada).</p>
      <div class="table-wrap">
        <table class="validation-table benchmark-validation-table">
          <thead>
            <tr>
              <th>Motor</th>
              <th>Global</th>
              <th>Violaciones</th>
              ${headers}
            </tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`;
  },
};
