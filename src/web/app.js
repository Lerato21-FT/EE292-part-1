const colors = {
  text: "#e9eef4",
  muted: "#8c9aaa",
  grid: "rgba(149, 168, 188, 0.13)",
  cyan: "#64dfd0",
  orange: "#ff9c6b",
};

const plotLayout = {
  paper_bgcolor: "#101923",
  plot_bgcolor: "#101923",
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

const plotConfig = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };
const elements = {
  error: document.querySelector("#error-message"),
  loading: document.querySelector("#loading-message"),
  results: document.querySelector("#results"),
  button: document.querySelector("#analyze-button"),
  uploadButton: document.querySelector("#upload-button"),
  datasetFolder: document.querySelector("#dataset-folder"),
  datasetStatus: document.querySelector("#dataset-status"),
  initialField: document.querySelector("#initial-field"),
  initialLinewidth: document.querySelector("#initial-linewidth"),
  traceSelect: document.querySelector("#trace-select"),
};

let measurements = [];
let geometry = "in_plane";
let activeGeometry = "in_plane";
let activeDatasetLabel = "Bundled demo data loaded";
let busy = false;
let traceRequest = 0;
let traceQuery = "";

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

function displayError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

function plotKittel(analysis) {
  const points = analysis.measurements;
  const fit = analysis.kittel_fit;
  const equation = analysis.geometry === "out_of_plane"
    ? "f = (g μB/h)<br>× (Bres − Beff,⊥)"
    : "f = (g μB/h) √[(Bres + B4)<br>× (Bres + B4 + Beff,⊥)]";
  const parameters = `g = ${fit.g_factor.toFixed(4)}<br>Beff,⊥ = ${fit.effective_perpendicular_field_t.toFixed(4)} T${fit.fourfold_field_t === null ? "" : `<br>B4 = ${fit.fourfold_field_t.toFixed(5)} T`}`;
  return Plotly.react(
    "kittel-chart",
    [
      {
        x: analysis.kittel_fit.curve.map((point) => point.field_oe),
        y: analysis.kittel_fit.curve.map((point) => point.frequency_ghz),
        type: "scatter",
        mode: "lines",
        name: "Kittel fit",
        line: { color: colors.cyan, width: 2.5 },
        hovertemplate: "%{x:.1f} Oe · %{y:.3f} GHz<extra>Kittel fit</extra>",
      },
      {
        x: points.map((point) => point.resonance_field_oe),
        y: points.map((point) => point.frequency_ghz),
        type: "scatter",
        mode: "markers",
        name: "Resonance points",
        marker: { color: colors.orange, size: 7, line: { color: "#101923", width: 1 } },
        customdata: points.map((point) => [point.filename, point.resonance_r_squared]),
        hovertemplate: "%{y:.3f} GHz · %{x:.1f} Oe<br>%{customdata[0]}<extra>Measured</extra>",
      },
    ],
    {
      ...plotLayout,
      xaxis: axis("Resonance field (Oe)", plotLayout.xaxis),
      yaxis: axis("Frequency (GHz)", plotLayout.yaxis),
      annotations: fitAnnotation(`${equation}<br>${parameters}`),
    },
    plotConfig,
  );
}

function plotLinewidth(analysis) {
  const points = analysis.measurements;
  return Plotly.react(
    "linewidth-chart",
    [
      {
        x: analysis.linewidth_fit.curve.map((point) => point.frequency_ghz),
        y: analysis.linewidth_fit.curve.map((point) => point.linewidth_pp_oe),
        type: "scatter",
        mode: "lines",
        name: "Linear fit",
        line: { color: colors.cyan, width: 2.5 },
      },
      {
        x: points.map((point) => point.frequency_ghz),
        y: points.map((point) => point.linewidth_pp_oe),
        type: "scatter",
        mode: "markers",
        name: "Measured linewidth",
        marker: { color: colors.orange, size: 7, line: { color: "#101923", width: 1 } },
        customdata: points.map((point) => [point.filename, point.resonance_r_squared]),
        hovertemplate: "%{x:.3f} GHz · %{y:.2f} Oe<br>%{customdata[0]}<extra>Measured</extra>",
      },
    ],
    {
      ...plotLayout,
      xaxis: axis("Frequency (GHz)", plotLayout.xaxis),
      yaxis: axis("ΔHpp (Oe)", plotLayout.yaxis),
      annotations: fitAnnotation(`ΔHpp = ΔH0 + (4πα/√3γ)·f<br>α = ${analysis.linewidth_fit.damping.toPrecision(4)}<br>ΔH0 = ${analysis.linewidth_fit.intercept_oe.toFixed(2)} Oe`),
    },
    plotConfig,
  );
}

async function showAnalysis(analysis) {
  const kittel = analysis.kittel_fit;
  const linewidth = analysis.linewidth_fit;
  document.querySelector("#sweep-count").textContent = String(analysis.measurements.length).padStart(2, "0");
  document.querySelector("#g-factor").textContent = kittel.g_factor.toFixed(4);
  document.querySelector("#perpendicular-field").textContent = kittel.effective_perpendicular_field_t.toFixed(4);
  document.querySelector("#fourfold-field").textContent = kittel.fourfold_field_t === null ? "N/A" : kittel.fourfold_field_t.toFixed(5);
  document.querySelector("#fourfold-note").textContent = kittel.fourfold_field_t === null ? "Not fitted in perpendicular geometry" : "Aligned-axis contribution, φ = 0°";
  document.querySelector("#damping").textContent = linewidth.damping.toPrecision(4);
  document.querySelector("#kittel-r2").textContent = `Kittel model R² ${kittel.r_squared.toFixed(5)}`;
  document.querySelector("#linewidth-r2").textContent = `Linewidth model R² ${linewidth.r_squared.toFixed(5)}`;
  document.querySelector("#kittel-equation").textContent = kittel.equation;
  document.querySelector("#linewidth-equation").textContent = linewidth.equation;
  document.querySelector("#kittel-model-label").textContent = analysis.geometry === "out_of_plane" ? "PERPENDICULAR KITTEL MODEL" : "ALIGNED-AXIS KITTEL MODEL";
  document.querySelector("#kittel-fit-label").textContent = `g = ${kittel.g_factor.toFixed(4)} · Beff,⊥ = ${kittel.effective_perpendicular_field_t.toFixed(4)} T${kittel.fourfold_field_t === null ? "" : ` · B4 = ${kittel.fourfold_field_t.toFixed(5)} T`}`;
  document.querySelector("#linewidth-fit-label").textContent = `α = ${linewidth.damping.toPrecision(4)} · ΔHpp,0 = ${linewidth.intercept_oe.toFixed(2)} Oe · slope = ${linewidth.slope_oe_per_ghz.toPrecision(4)} Oe/GHz`;
  document.querySelector("#model-note").textContent = analysis.geometry === "out_of_plane"
    ? "Model scope. The perpendicular Kittel model assumes a saturated film with magnetization aligned to a nonnegative applied field normal to the film. Beff,⊥ = μ₀Ms − μ₀H₂⊥; a negative value means perpendicular anisotropy exceeds the demagnetizing field. It is an effective field, not intrinsic Ku. No in-plane four-fold field is inferred. The −0.4 T and 10 Oe values initialize the fits; linewidth is measured peak-to-peak from the derivative signal."
    : "Model scope. The in-plane Kittel fit assumes the aligned 0° axis. Beff,⊥ = μ₀Ms − μ₀H₂⊥ is an effective field, not intrinsic Ku; extracting Ku requires independent Ms. A single azimuth cannot establish four-fold angular symmetry. Linewidth is measured peak-to-peak from the derivative signal.";
  await Promise.all([plotKittel(analysis), plotLinewidth(analysis)]);
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
        x: trace.field_oe,
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
      annotations: fitAnnotation(`Derivative Lorentzian<br>+ linear background<br>Hres = ${trace.resonance_field_oe.toFixed(2)} Oe<br>ΔHpp = ${trace.linewidth_pp_oe.toFixed(2)} Oe`),
    },
    plotConfig,
  );
  document.querySelector("#trace-summary").textContent =
    `${trace.frequency_ghz.toFixed(3)} GHz  ·  Hres ${trace.resonance_field_oe.toFixed(2)} Oe  ·  ΔHpp ${trace.linewidth_pp_oe.toFixed(2)} Oe  ·  trace R² ${trace.r_squared.toFixed(5)}`;
  document.querySelector("#save-trace-button").dataset.filename =
    `fmr-trace-${trace.frequency_ghz.toFixed(3)}-GHz`;
}

async function analyze(restoreActiveDataset = false) {
  if (busy || geometry !== activeGeometry) return;
  elements.error.hidden = true;
  elements.results.hidden = true;
  elements.loading.hidden = false;
  setBusy(true);
  try {
    const query = restoreActiveDataset ? new URLSearchParams() : analysisQuery();
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
    elements.traceSelect.replaceChildren(
      ...measurements.map((measurement) => {
        const option = document.createElement("option");
        option.value = measurement.measurement_id;
        option.textContent = `${measurement.frequency_ghz.toFixed(3)} GHz`;
        return option;
      }),
    );
    elements.results.hidden = false;
    await showAnalysis(analysis);
    await showTrace(elements.traceSelect.value);
  } catch (error) {
    displayError(error.message);
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
  elements.results.hidden = true;
  elements.loading.hidden = false;
  elements.loading.textContent = "Validating uploaded sweeps and fitting the selected geometry…";
  elements.datasetStatus.textContent = `Uploading ${csvFiles.length} CSV files…`;
  try {
    const query = analysisQuery();
    const result = await requestJson(`/api/datasets?${query}`, { method: "POST", body: formData });
    activeGeometry = result.geometry;
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

async function savePlot(chartId, filename) {
  try {
    await Plotly.downloadImage(chartId, {
      format: "png",
      filename: `${filename}-${geometry}`,
      width: 1000,
      height: 700,
      scale: 2,
    });
  } catch (error) {
    displayError(`Could not save plot: ${error.message}`);
  }
}

elements.button.addEventListener("click", () => analyze());
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
    elements.results.hidden = true;
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
