// Plot colours come from the active theme's CSS tokens, so the plots follow Light/Dark.
// One meaning each: data = orange, model = cyan, selected = violet, excluded = muted cross.
function readColors() {
  const style = getComputedStyle(document.documentElement);
  const token = (name) => style.getPropertyValue(name).trim();
  return {
    text: token("--text"),
    muted: token("--muted"),
    // Plotly needs the comma form of rgba().
    grid: `rgba(${token("--line-rgb").split(/\s+/).join(", ")}, 0.16)`,
    panel: token("--panel"),
    cyan: token("--cyan"),
    orange: token("--orange"),
    violet: token("--violet"),
  };
}

function buildLayout() {
  return {
    paper_bgcolor: colors.panel,
    plot_bgcolor: colors.panel,
    font: { family: "SFMono-Regular, Consolas, monospace", size: 11, color: colors.muted },
    margin: { l: 74, r: 26, t: 148, b: 66 },
    autosize: true,
    hovermode: "closest",
    xaxis: {
      gridcolor: colors.grid,
      zerolinecolor: colors.grid,
      linecolor: colors.grid,
      tickcolor: colors.grid,
      automargin: true,
      nticks: 5,
      tickformat: ".4~g",
    },
    yaxis: {
      gridcolor: colors.grid,
      zerolinecolor: colors.grid,
      linecolor: colors.grid,
      tickcolor: colors.grid,
      automargin: true,
      nticks: 5,
      tickformat: ".4~g",
    },
    legend: { orientation: "h", y: 1.02, yanchor: "bottom", x: 0, font: { size: 10 }, traceorder: "normal", entrywidth: 165, entrywidthmode: "pixels" },
    showlegend: true,
  };
}

let colors = readColors();
let plotLayout = buildLayout();

// Typeset model equations. These are fixed presentation strings, never user data.
const mi = (name) => `<mi>${name}</mi>`;
const sub = (base, index) => `<msub>${base}<mtext>${index}</mtext></msub>`;
const B = (index) => sub(mi("B"), index);
const prefactor = `<mfrac><mrow>${mi("g")}${sub(mi("μ"), "B")}</mrow>${mi("h")}</mfrac>`;
const EQUATIONS = {
  in_plane: `<math display="block">${mi("f")}<mo>=</mo>${prefactor}<msqrt><mrow><mo>(</mo>${B("res")}<mo>+</mo>${B("4")}<mo>)</mo><mo>(</mo>${B("res")}<mo>+</mo>${B("4")}<mo>+</mo>${B("eff,⊥")}<mo>)</mo></mrow></msqrt></math>`,
  out_of_plane: `<math display="block">${mi("f")}<mo>=</mo>${prefactor}<mo>(</mo>${B("res")}<mo>−</mo>${B("eff,⊥")}<mo>)</mo></math>`,
  linewidth: `<math display="block">${sub("<mrow><mi mathvariant=\"normal\">Δ</mi><mi>H</mi></mrow>", "pp")}<mo>=</mo>${sub("<mrow><mi mathvariant=\"normal\">Δ</mi><mi>H</mi></mrow>", "0")}<mo>+</mo><mfrac><mrow><mn>4</mn><mi>π</mi><mi>α</mi></mrow><mrow><msqrt><mn>3</mn></msqrt><mi>γ</mi></mrow></mfrac><mo>·</mo>${mi("f")}</math>`,
};

const MODEL_SCOPE = {
  in_plane: [
    ["Aligned axis.", "The field lies along the 0° in-plane axis. One azimuth cannot establish four-fold angular symmetry, so B4 is the contribution along this axis only."],
    ["Effective field, not Ku.", "Beff,⊥ = μ₀Ms − μ₀H₂⊥ combines demagnetization and anisotropy. Separating Ku needs an independent Ms."],
    ["Beff,⊥ > 0 by assumption.", "The same curve is also fitted by a mirror solution with Beff,⊥ < 0. The app warns when the data cannot rule it out."],
    ["Peak-to-peak linewidth.", "ΔHpp is the width of the fitted derivative Lorentzian; strong field modulation broadens it."],
  ],
  out_of_plane: [
    ["Saturated film.", "The magnetization is assumed parallel to a nonnegative field normal to the film."],
    ["Signed effective field, not Ku.", "Beff,⊥ = μ₀Ms − μ₀H₂⊥; a negative value means perpendicular anisotropy exceeds the demagnetizing field."],
    ["No four-fold term.", "No in-plane B4 is inferred in this geometry."],
    ["Starting values only.", "−0.4 T and 10 Oe seed the fits; the measured sweeps determine the results."],
    ["Peak-to-peak linewidth.", "ΔHpp is the width of the fitted derivative Lorentzian; strong field modulation broadens it."],
  ],
};

// Print-friendly styling applied only to exported PNGs; the page keeps its dark theme.
const exportColors = { text: "#1b2430", muted: "#5b6672", grid: "#e3e8ee", line: "#0f8f84", point: "#d9622b", selected: "#6d4ad6" };

const plotConfig = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };
const elements = {
  error: document.querySelector("#error-message"),
  loading: document.querySelector("#loading-message"),
  results: document.querySelector("#results"),
  resultsSummary: document.querySelector("#results-summary"),
  button: document.querySelector("#analyze-button"),
  uploadButton: document.querySelector("#upload-button"),
  datasetFolder: document.querySelector("#dataset-folder"),
  datasetStatus: document.querySelector("#dataset-status"),
  initialField: document.querySelector("#initial-field"),
  initialLinewidth: document.querySelector("#initial-linewidth"),
  traceSelect: document.querySelector("#trace-select"),
  datasetSelection: document.querySelector("#dataset-selection"),
  excludeSelected: document.querySelector("#exclude-selected"),
  restoreSelected: document.querySelector("#restore-selected"),
  restoreAll: document.querySelector("#restore-all"),
  selectionStatus: document.querySelector("#selection-status"),
};

let measurements = [];
let geometry = "in_plane";
let activeGeometry = "in_plane";
let activeDatasetLabel = "Bundled demo data loaded";
let busy = false;
let traceRequest = 0;
let traceQuery = "";
let excludedIds = new Set();
let selectedIds = new Set();
let lastAnalysis = null;

// The summary sits above the controls and the details below them; they show and hide together.
function setResultsHidden(hidden) {
  elements.results.hidden = hidden;
  elements.resultsSummary.hidden = hidden;
}

function updateSelectionControls() {
  elements.datasetSelection.disabled = busy;
  elements.excludeSelected.disabled = busy || ![...selectedIds].some((id) => !excludedIds.has(id));
  elements.restoreSelected.disabled = busy || ![...selectedIds].some((id) => excludedIds.has(id));
  elements.restoreAll.disabled = busy || excludedIds.size === 0;
  elements.selectionStatus.textContent = `${selectedIds.size} selected · ${excludedIds.size} excluded from both fits`;
  for (const option of elements.datasetSelection.options) option.selected = selectedIds.has(option.value);
}

function pointMarkers(points) {
  return {
    color: points.map((point) => selectedIds.has(point.measurement_id) ? colors.violet : point.excluded ? colors.muted : colors.orange),
    symbol: points.map((point) => point.excluded ? "x" : "circle"),
    size: points.map((point) => selectedIds.has(point.measurement_id) ? 11 : 7),
    line: { color: colors.panel, width: 1 },
  };
}

async function redrawSelection() {
  updateSelectionControls();
  await Promise.all([plotKittel(lastAnalysis), plotLinewidth(lastAnalysis)]);
}

function bindPointSelection() {
  for (const chartId of ["kittel-chart", "linewidth-chart"]) {
    const chart = document.getElementById(chartId);
    chart.removeAllListeners("plotly_click");
    chart.on("plotly_click", (event) => {
      if (busy) return;
      const point = event.points.find((item) => item.curveNumber === 1);
      if (!point) return;
      const id = point.customdata[0];
      if (selectedIds.has(id)) selectedIds.delete(id);
      else selectedIds.add(id);
      redrawSelection().catch((error) => displayError(error.message));
    });
  }
}

async function applyExclusions(action) {
  if (busy) return;
  const next = new Set(excludedIds);
  if (action === "restore-all") next.clear();
  else for (const id of selectedIds) {
    if (action === "exclude") next.add(id);
    else next.delete(id);
  }
  await analyze(false, next);
}

function updateGeometryControls() {
  const perpendicular = geometry === "out_of_plane";
  elements.initialField.min = perpendicular ? "-2" : "0";
  elements.initialField.value = perpendicular ? "-0.4" : "0.9";
  document.querySelector("#linewidth-control").hidden = !perpendicular;
  document.querySelector("#geometry-heading").textContent = perpendicular ? "OUT-OF-PLANE GEOMETRY" : "IN-PLANE GEOMETRY";
  document.querySelectorAll("[data-geometry]").forEach((item) => {
    item.setAttribute("aria-pressed", String(item.dataset.geometry === geometry));
  });
}

function axis(title, base) {
  return { ...base, title: { text: title, standoff: 16, font: { size: 11 } } };
}

function fitAnnotation(text) {
  return [{ xref: "paper", yref: "paper", x: 0, y: 1, xanchor: "left", yanchor: "bottom",
    yshift: 64, text, showarrow: false, align: "left", font: { size: 10, color: colors.text } }];
}

function setBusy(value) {
  busy = value;
  elements.button.disabled = value || geometry !== activeGeometry;
  elements.uploadButton.disabled = value;
  elements.initialField.disabled = value;
  elements.initialLinewidth.disabled = value;
  elements.traceSelect.disabled = value;
  document.querySelectorAll("[data-geometry], .download-button").forEach((button) => {
    button.disabled = value;
  });
  elements.results.setAttribute("aria-busy", String(value));
  updateSelectionControls();
}

function analysisQuery() {
  const field = Number(elements.initialField.value);
  const minimum = geometry === "out_of_plane" ? -2 : 0;
  if (elements.initialField.value.trim() === "" || !Number.isFinite(field) || field < minimum || field > 2) {
    throw new Error(`Initial effective perpendicular field must be between ${minimum} and 2 T.`);
  }
  const query = new URLSearchParams({ geometry, initial_perpendicular_field_t: field });
  if (geometry === "out_of_plane") {
    const linewidth = Number(elements.initialLinewidth.value);
    if (!Number.isFinite(linewidth) || linewidth <= 0 || linewidth > 10000) {
      throw new Error("Initial peak-to-peak linewidth must be greater than 0 and at most 10000 Oe.");
    }
    query.set("initial_linewidth_pp_oe", linewidth);
  }
  return query;
}

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    const message = Array.isArray(body.detail)
      ? body.detail.map((item) => `${item.loc.at(-1)}: ${item.msg}`).join("; ")
      : body.detail;
    throw new Error(message || `Request failed (${response.status}).`);
  }
  return body;
}

// Formats a backend value and its backend 1σ standard error; nothing is computed here.
function withSigma(value, sigma, format) {
  return sigma === null || sigma === undefined ? format(value) : `${format(value)} ± ${sigma.toPrecision(2)}`;
}

function sigmaText(sigma, unit = "") {
  return sigma === null || sigma === undefined ? "" : `± ${sigma.toPrecision(2)}${unit} (1σ)`;
}

function displayError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

function plotKittel(analysis) {
  const points = analysis.measurements;
  const fit = analysis.kittel_fit;
  const equation = analysis.geometry === "out_of_plane"
    ? "f = (g μ<sub>B</sub>/h)(B<sub>res</sub> − B<sub>eff,⊥</sub>)"
    : "f = (g μ<sub>B</sub>/h) √[(B<sub>res</sub> + B<sub>4</sub>)<br>× (B<sub>res</sub> + B<sub>4</sub> + B<sub>eff,⊥</sub>)]";
  const parameters = fit ? `g = ${withSigma(fit.g_factor, fit.g_factor_sigma, (v) => v.toFixed(4))}<br>B<sub>eff,⊥</sub> = ${withSigma(fit.effective_perpendicular_field_t, fit.effective_perpendicular_field_sigma_t, (v) => v.toFixed(4))} T${fit.fourfold_field_t === null ? "" : `<br>B<sub>4</sub> = ${withSigma(fit.fourfold_field_t, fit.fourfold_field_sigma_t, (v) => v.toFixed(5))} T`}` : "";
  const curve = fit?.curve ?? [];
  return Plotly.react(
    "kittel-chart",
    [
      {
        x: curve.map((point) => point.field_oe),
        y: curve.map((point) => point.frequency_ghz),
        type: "scatter",
        mode: "lines",
        name: "Kittel fit",
        line: { color: colors.cyan, width: 2.5 },
        hoverinfo: "skip",
      },
      {
        x: points.map((point) => point.resonance_field_oe),
        y: points.map((point) => point.frequency_ghz),
        type: "scatter",
        mode: "markers",
        name: "Resonance points",
        marker: pointMarkers(points),
        customdata: points.map((point) => [point.measurement_id, point.excluded ? "Excluded from both fits" : "Included in both fits"]),
        hovertemplate: "%{y:.3f} GHz · %{x:.1f} Oe<br>%{customdata[0]}<br>%{customdata[1]}<extra>Click to select</extra>",
      },
    ],
    {
      ...plotLayout,
      xaxis: axis("Resonance field B<sub>res</sub> (Oe)", plotLayout.xaxis),
      yaxis: axis("Frequency f (GHz)", plotLayout.yaxis),
      annotations: fitAnnotation(fit ? `${equation}<br>${parameters}` : "Kittel fit unavailable<br>Inspect or exclude sweeps"),
    },
    plotConfig,
  );
}

function plotLinewidth(analysis) {
  const points = analysis.measurements;
  const fit = analysis.linewidth_fit;
  const curve = fit?.curve ?? [];
  return Plotly.react(
    "linewidth-chart",
    [
      {
        x: curve.map((point) => point.frequency_ghz),
        y: curve.map((point) => point.linewidth_pp_oe),
        type: "scatter",
        mode: "lines",
        name: "Linear fit",
        line: { color: colors.cyan, width: 2.5 },
        hoverinfo: "skip",
      },
      {
        x: points.map((point) => point.frequency_ghz),
        y: points.map((point) => point.linewidth_pp_oe),
        type: "scatter",
        mode: "markers",
        name: "Measured linewidth",
        marker: pointMarkers(points),
        customdata: points.map((point) => [point.measurement_id, point.excluded ? "Excluded from both fits" : "Included in both fits"]),
        hovertemplate: "%{x:.3f} GHz · %{y:.2f} Oe<br>%{customdata[0]}<br>%{customdata[1]}<extra>Click to select</extra>",
      },
    ],
    {
      ...plotLayout,
      xaxis: axis("Frequency f (GHz)", plotLayout.xaxis),
      yaxis: axis("Linewidth ΔH<sub>pp</sub> (Oe)", plotLayout.yaxis),
      annotations: fitAnnotation(fit ? `ΔH<sub>pp</sub> = ΔH<sub>0</sub> + (4πα/√3γ)·f<br>α = ${withSigma(fit.damping, fit.damping_sigma, (v) => v.toPrecision(4))}<br>ΔH<sub>0</sub> = ${withSigma(fit.intercept_oe, fit.intercept_sigma_oe, (v) => v.toFixed(2))} Oe${fit.damping_established ? "" : "<br>α not established: see warnings"}` : "Linewidth fit unavailable<br>Inspect or exclude sweeps"),
    },
    plotConfig,
  );
}

// Shows a typeset equation when the backend reports that fit; the API string is the accessible label.
function showEquation(selector, apiEquation, mathml) {
  const target = document.querySelector(selector);
  if (apiEquation) {
    target.innerHTML = mathml;
    target.setAttribute("aria-label", apiEquation);
  } else {
    target.textContent = "Fit unavailable";
    target.removeAttribute("aria-label");
  }
}

async function showAnalysis(analysis) {
  const kittel = analysis.kittel_fit;
  const linewidth = analysis.linewidth_fit;
  const fitStatus = document.querySelector("#fit-status");
  fitStatus.hidden = !analysis.fit_error && !analysis.linewidth_fit_error;
  fitStatus.textContent = analysis.fit_error
    ? `Magnetic-property fits unavailable. ${analysis.fit_error}`
    : analysis.linewidth_fit_error ? `Damping unavailable; the Kittel fit is still reported. ${analysis.linewidth_fit_error}` : "";
  document.querySelector("#result-summary").replaceChildren(...analysis.summary.map((text) => {
    const sentence = document.createElement("p");
    sentence.textContent = text;
    return sentence;
  }));
  const warnings = document.querySelector("#fit-warnings");
  warnings.replaceChildren(...analysis.warnings.map((text) => {
    const item = document.createElement("li");
    item.textContent = text;
    return item;
  }));
  warnings.hidden = analysis.warnings.length === 0;
  document.querySelector("#g-factor-sigma").textContent = sigmaText(kittel?.g_factor_sigma);
  document.querySelector("#perpendicular-field-sigma").textContent = sigmaText(kittel?.effective_perpendicular_field_sigma_t, " T");
  document.querySelector("#fourfold-field-sigma").textContent = sigmaText(kittel?.fourfold_field_sigma_t, " T");
  const dampingEstablished = Boolean(linewidth?.damping_established);
  document.querySelector("#damping-card").classList.toggle("metric-accent", dampingEstablished);
  document.querySelector("#damping-status").hidden = !linewidth || dampingEstablished;
  document.querySelector("#damping-sigma").textContent = linewidth ? `${sigmaText(linewidth.damping_sigma)}${dampingEstablished ? "" : " · see warnings"}` : "";
  const perpendicularNote = document.querySelector("#perpendicular-note");
  if (kittel?.mirror_effective_perpendicular_field_t != null) {
    perpendicularNote.textContent = `Mirror fits equally: ${kittel.mirror_effective_perpendicular_field_t.toFixed(4)} T with B₄ = ${kittel.mirror_fourfold_field_t.toFixed(5)} T`;
  } else {
    perpendicularNote.innerHTML = "μ₀M<sub>eff</sub> = μ₀M<sub>s</sub> − μ₀H<sub>2⊥</sub>";
  }
  document.querySelector("#sweep-count").textContent = String(analysis.included_measurement_count).padStart(2, "0");
  document.querySelector("#g-factor").textContent = kittel?.g_factor.toFixed(4) ?? "—";
  document.querySelector("#perpendicular-field").textContent = kittel?.effective_perpendicular_field_t.toFixed(4) ?? "—";
  document.querySelector("#fourfold-field").textContent = kittel ? (kittel.fourfold_field_t === null ? "N/A" : kittel.fourfold_field_t.toFixed(5)) : "—";
  document.querySelector("#fourfold-note").textContent = kittel ? (kittel.fourfold_field_t === null ? "Not fitted in perpendicular geometry" : "Aligned-axis contribution, φ = 0°") : "Fit unavailable";
  document.querySelector("#damping").textContent = linewidth?.damping.toPrecision(4) ?? "—";
  document.querySelector("#kittel-r2").textContent = kittel ? `Kittel model R² ${kittel.r_squared.toFixed(5)}` : "Kittel fit unavailable";
  document.querySelector("#linewidth-r2").textContent = linewidth ? `Linewidth model R² ${linewidth.r_squared.toFixed(5)}` : "Linewidth fit unavailable";
  showEquation("#kittel-equation", kittel?.equation, EQUATIONS[analysis.geometry]);
  showEquation("#linewidth-equation", linewidth?.equation, EQUATIONS.linewidth);
  document.querySelector("#kittel-model-label").textContent = analysis.geometry === "out_of_plane" ? "PERPENDICULAR KITTEL MODEL" : "ALIGNED-AXIS KITTEL MODEL";
  document.querySelector("#kittel-fit-label").textContent = kittel ? `g = ${withSigma(kittel.g_factor, kittel.g_factor_sigma, (v) => v.toFixed(4))} · Beff,⊥ = ${withSigma(kittel.effective_perpendicular_field_t, kittel.effective_perpendicular_field_sigma_t, (v) => v.toFixed(4))} T${kittel.fourfold_field_t === null ? "" : ` · B4 = ${withSigma(kittel.fourfold_field_t, kittel.fourfold_field_sigma_t, (v) => v.toFixed(5))} T`} (1σ)` : "No magnetic properties reported until the Kittel model can be fitted.";
  document.querySelector("#linewidth-fit-label").textContent = linewidth ? `α = ${withSigma(linewidth.damping, linewidth.damping_sigma, (v) => v.toPrecision(4))} · ΔHpp,0 = ${withSigma(linewidth.intercept_oe, linewidth.intercept_sigma_oe, (v) => v.toFixed(2))} Oe · slope = ${withSigma(linewidth.slope_oe_per_ghz, linewidth.slope_sigma_oe_per_ghz, (v) => v.toPrecision(4))} Oe/GHz (1σ)` : "No damping reported until the linewidth model can be fitted.";
  document.querySelector("#model-note").replaceChildren(...MODEL_SCOPE[analysis.geometry].map(([head, text]) => {
    const item = document.createElement("li");
    const strong = document.createElement("b");
    strong.textContent = head;
    item.append(strong, ` ${text}`);
    return item;
  }));
  await Promise.all([plotKittel(analysis), plotLinewidth(analysis)]);
  bindPointSelection();
}

async function showTrace(measurementId) {
  const request = ++traceRequest;
  const trace = await requestJson(`/api/measurements/${encodeURIComponent(measurementId)}${traceQuery}`);
  if (request !== traceRequest) return;
  await Plotly.react(
    "trace-chart",
    [
      {
        x: trace.field_oe,
        y: trace.signal,
        type: "scatter",
        mode: "lines",
        name: "Lock-in signal",
        line: { color: colors.orange, width: 1.2 },
      },
      {
        x: trace.extraction_error ? [] : trace.field_oe,
        y: trace.fit_signal,
        type: "scatter",
        mode: "lines",
        name: "Derivative fit",
        line: { color: colors.cyan, width: 2 },
      },
    ],
    {
      ...plotLayout,
      xaxis: axis("Magnetic field (Oe)", plotLayout.xaxis),
      yaxis: axis("Lock-in signal (a.u.)", plotLayout.yaxis),
      annotations: fitAnnotation(trace.extraction_error ? "Resonance fit unavailable<br>Raw samples shown" : `Derivative Lorentzian<br>+ linear background<br>Hres = ${trace.resonance_field_oe.toFixed(2)} Oe<br>ΔHpp = ${trace.linewidth_pp_oe.toFixed(2)} Oe`),
    },
    plotConfig,
  );
  document.querySelector("#trace-summary").textContent =
    trace.extraction_error ? `${trace.frequency_ghz.toFixed(3)} GHz · Raw trace · ${trace.extraction_error}` : `${trace.frequency_ghz.toFixed(3)} GHz  ·  Hres ${trace.resonance_field_oe.toFixed(2)} Oe  ·  ΔHpp ${trace.linewidth_pp_oe.toFixed(2)} Oe  ·  trace R² ${trace.r_squared.toFixed(5)}${trace.low_quality ? " (below 0.98: inspect)" : ""}`;
  document.querySelector("#save-trace-button").dataset.filename =
    `fmr-trace-${trace.frequency_ghz.toFixed(3)}-GHz`;
}

async function analyze(restoreActiveDataset = false, requestedExclusions = excludedIds) {
  if (busy || geometry !== activeGeometry) return;
  elements.error.hidden = true;
  setResultsHidden(true);
  elements.loading.hidden = false;
  elements.loading.textContent = "Extracting resonance points and fitting magnetic properties…";
  setBusy(true);
  try {
    const query = restoreActiveDataset ? new URLSearchParams() : analysisQuery();
    if (!restoreActiveDataset) {
      for (const id of requestedExclusions) query.append("excluded_measurement_ids", id);
    }
    const analysis = await requestJson(
      `/api/analysis?${query}`,
    );
    if (restoreActiveDataset) {
      geometry = analysis.geometry;
      activeGeometry = geometry;
      updateGeometryControls();
      elements.initialField.value = String(analysis.initial_perpendicular_field_t);
      elements.initialLinewidth.value = String(analysis.initial_linewidth_pp_oe ?? 10);
      activeDatasetLabel = `${analysis.measurements.length} ${geometry === "out_of_plane" ? "out-of-plane" : "in-plane"} sweeps active`;
      elements.datasetStatus.textContent = activeDatasetLabel;
    }
    traceQuery = query.has("initial_linewidth_pp_oe") ? `?initial_linewidth_pp_oe=${query.get("initial_linewidth_pp_oe")}` : "";
    measurements = analysis.measurements;
    lastAnalysis = analysis;
    excludedIds = new Set(measurements.filter((point) => point.excluded).map((point) => point.measurement_id));
    selectedIds.clear();
    elements.datasetSelection.replaceChildren(...measurements.map((measurement) => {
      const option = document.createElement("option");
      option.value = measurement.measurement_id;
      const resonance = measurement.extraction_error ? "resonance fit unavailable" : `Hres ${measurement.resonance_field_oe.toFixed(2)} Oe`;
      const flags = `${measurement.low_quality ? ` · low R² ${measurement.resonance_r_squared.toFixed(3)}` : ""}${measurement.modulation_warning ? " · modulation > ΔHpp/3" : ""}`;
      option.textContent = `${measurement.frequency_ghz.toFixed(3)} GHz · ${measurement.excluded ? "excluded" : "included"} · ${resonance}${flags} · ${measurement.filename}`;
      return option;
    }));
    elements.traceSelect.replaceChildren(
      ...measurements.map((measurement) => {
        const option = document.createElement("option");
        option.value = measurement.measurement_id;
        option.textContent = `${measurement.frequency_ghz.toFixed(3)} GHz${measurement.excluded ? " · excluded" : ""}${measurement.extraction_error ? " · fit unavailable" : ""}`;
        return option;
      }),
    );
    setResultsHidden(false);
    await showAnalysis(analysis);
    await showTrace(elements.traceSelect.value);
  } catch (error) {
    displayError(error.message);
    if (lastAnalysis && lastAnalysis.geometry === geometry) setResultsHidden(false);
  } finally {
    elements.loading.hidden = true;
    setBusy(false);
  }
}

async function uploadDataset() {
  if (busy) return;
  elements.error.hidden = true;
  const csvFiles = Array.from(elements.datasetFolder.files).filter((file) =>
    file.name.toLowerCase().endsWith(".csv"),
  );
  if (csvFiles.length === 0) {
    displayError("Choose a folder containing CSV measurement files.");
    return;
  }

  const formData = new FormData();
  for (const file of csvFiles) {
    formData.append("files", file, file.webkitRelativePath || file.name);
  }

  setBusy(true);
  setResultsHidden(true);
  elements.loading.hidden = false;
  elements.loading.textContent = "Validating uploaded CSV files…";
  elements.datasetStatus.textContent = `Uploading ${csvFiles.length} CSV files…`;
  try {
    const query = analysisQuery();
    const result = await requestJson(`/api/datasets?${query}`, { method: "POST", body: formData });
    activeGeometry = result.geometry;
    excludedIds.clear();
    selectedIds.clear();
    lastAnalysis = null;
    activeDatasetLabel = `${result.measurement_count} uploaded ${geometry === "out_of_plane" ? "out-of-plane" : "in-plane"} CSV sweeps active`;
    elements.datasetStatus.textContent = activeDatasetLabel;
    setBusy(false);
    await analyze();
  } catch (error) {
    elements.datasetStatus.textContent = "Upload rejected; the previous dataset is still active";
    displayError(error.message);
  } finally {
    setBusy(false);
    elements.loading.hidden = true;
    elements.datasetFolder.value = "";
  }
}

function recolor(color) {
  if (Array.isArray(color)) return color.map(recolor);
  return {
    [colors.cyan]: exportColors.line,
    [colors.orange]: exportColors.point,
    [colors.violet]: exportColors.selected,
    [colors.muted]: "#9aa5b1",
  }[color] ?? color;
}

function exportAxis(base) {
  return {
    ...base,
    gridcolor: exportColors.grid,
    zerolinecolor: exportColors.grid,
    linecolor: exportColors.muted,
    tickcolor: exportColors.muted,
    showline: true,
    mirror: true,
    ticks: "outside",
    title: { ...base.title, font: { size: 20, color: exportColors.text } },
  };
}

// Re-renders the current chart on a white, larger-type layout for reports and slides.
function exportFigure(chart) {
  const data = chart.data.map((trace) => {
    const copy = { ...trace };
    if (trace.line) copy.line = { ...trace.line, color: recolor(trace.line.color), width: 3 };
    if (trace.marker) {
      copy.marker = {
        ...trace.marker,
        color: recolor(trace.marker.color),
        size: Array.isArray(trace.marker.size) ? trace.marker.size.map((size) => size + 4) : trace.marker.size,
        line: { color: "#ffffff", width: 1 },
      };
    }
    return copy;
  });
  const layout = {
    ...chart.layout,
    paper_bgcolor: "#ffffff",
    plot_bgcolor: "#ffffff",
    font: { family: "Helvetica, Arial, sans-serif", size: 16, color: exportColors.muted },
    margin: { l: 110, r: 50, t: 210, b: 100 },
    xaxis: exportAxis(chart.layout.xaxis),
    yaxis: exportAxis(chart.layout.yaxis),
    legend: { ...chart.layout.legend, font: { size: 16, color: exportColors.text }, entrywidth: 260 },
    annotations: (chart.layout.annotations ?? []).map((note) => ({
      ...note, yshift: 56, font: { size: 17, color: exportColors.text },
    })),
  };
  return { data, layout };
}

async function savePlot(chartId, filename) {
  try {
    const url = await Plotly.toImage(exportFigure(document.getElementById(chartId)), {
      format: "png",
      width: 1200,
      height: 850,
      scale: 2,
    });
    const link = document.createElement("a");
    link.href = url;
    link.download = `${filename}-${geometry}.png`;
    document.body.append(link);
    link.click();
    link.remove();
  } catch (error) {
    displayError(`Could not save plot: ${error.message}`);
  }
}

// Light is the default theme; a choice is remembered in this browser only.
function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]').content = theme === "dark" ? "#0a1018" : "#f6f8fa";
  document.querySelectorAll("[data-theme-choice]").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.themeChoice === theme));
  });
  colors = readColors();
  plotLayout = buildLayout();
}

function storedTheme() {
  try {
    return localStorage.getItem("fmr-theme") === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

applyTheme(storedTheme());
document.querySelectorAll("[data-theme-choice]").forEach((button) => {
  button.addEventListener("click", () => {
    const theme = button.dataset.themeChoice;
    try {
      localStorage.setItem("fmr-theme", theme);
    } catch {
      // Storage can be unavailable (private window); the theme still applies for this visit.
    }
    applyTheme(theme);
    if (lastAnalysis && !elements.results.hidden) {
      Promise.all([plotKittel(lastAnalysis), plotLinewidth(lastAnalysis), showTrace(elements.traceSelect.value)])
        .catch((error) => displayError(error.message));
    }
  });
});

const aboutDialog = document.querySelector("#about-dialog");
document.querySelector("#about-button").addEventListener("click", () => aboutDialog.showModal());
document.querySelector("#about-close").addEventListener("click", () => aboutDialog.close());
aboutDialog.addEventListener("click", (event) => {
  if (event.target === aboutDialog) aboutDialog.close();
});

elements.button.addEventListener("click", () => analyze());
elements.excludeSelected.addEventListener("click", () => applyExclusions("exclude"));
elements.restoreSelected.addEventListener("click", () => applyExclusions("restore"));
elements.restoreAll.addEventListener("click", () => applyExclusions("restore-all"));
elements.datasetSelection.addEventListener("change", () => {
  selectedIds = new Set([...elements.datasetSelection.selectedOptions].map((option) => option.value));
  redrawSelection().catch((error) => displayError(error.message));
});
elements.uploadButton.addEventListener("click", () => elements.datasetFolder.click());
elements.datasetFolder.addEventListener("change", () => {
  const csvCount = Array.from(elements.datasetFolder.files).filter((file) =>
    file.name.toLowerCase().endsWith(".csv"),
  ).length;
  if (csvCount > 0) {
    uploadDataset();
  } else {
    elements.datasetStatus.textContent = activeDatasetLabel;
  }
});
document.querySelectorAll("[data-geometry]").forEach((button) => {
  button.addEventListener("click", () => {
    if (busy || geometry === button.dataset.geometry) return;
    geometry = button.dataset.geometry;
    ++traceRequest;
    setResultsHidden(true);
    elements.error.hidden = true;
    updateGeometryControls();
    elements.datasetStatus.textContent = geometry === activeGeometry ? activeDatasetLabel : `Choose an ${geometry === "out_of_plane" ? "out-of-plane" : "in-plane"} folder to begin`;
    setBusy(false);
    if (geometry === activeGeometry) analyze();
  });
});

const chartObserver = new ResizeObserver((entries) => {
  for (const { target } of entries) {
    if (!elements.results.hidden && target._fullLayout && target.clientWidth > 0) {
      Plotly.Plots.resize(target).catch((error) => displayError(`Could not resize plot: ${error.message}`));
    }
  }
});
document.querySelectorAll(".chart").forEach((chart) => chartObserver.observe(chart));
document.querySelectorAll(".download-button").forEach((button) => {
  button.addEventListener("click", () => {
    savePlot(button.dataset.chart, button.dataset.filename);
  });
});
elements.traceSelect.addEventListener("change", () => {
  showTrace(elements.traceSelect.value).catch((error) => displayError(error.message));
});
analyze(true);
