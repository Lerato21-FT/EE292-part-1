const colors = {
  text: "#e9eef4",
  muted: "#8c9aaa",
  grid: "rgba(149, 168, 188, 0.13)",
  cyan: "#64dfd0",
  orange: "#ff9c6b",
};

const plotLayout = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "IBM Plex Mono, monospace", size: 10, color: colors.muted },
  margin: { l: 58, r: 22, t: 12, b: 50 },
  xaxis: {
    gridcolor: colors.grid,
    zerolinecolor: colors.grid,
    linecolor: colors.grid,
    tickcolor: colors.grid,
    titlefont: { size: 10, color: colors.muted },
  },
  yaxis: {
    gridcolor: colors.grid,
    zerolinecolor: colors.grid,
    linecolor: colors.grid,
    tickcolor: colors.grid,
    titlefont: { size: 10, color: colors.muted },
  },
  legend: { orientation: "h", y: 1.12, x: 0, font: { size: 10 } },
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
  traceSelect: document.querySelector("#trace-select"),
};

let measurements = [];

async function requestJson(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || `Request failed (${response.status}).`);
  }
  return body;
}

function displayError(message) {
  elements.error.textContent = message;
  elements.error.hidden = false;
}

function plotKittel(analysis) {
  const points = analysis.measurements;
  Plotly.react(
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
        name: "Measured resonances",
        marker: { color: colors.orange, size: 7, line: { color: "#101923", width: 1 } },
        customdata: points.map((point) => [point.filename, point.resonance_r_squared]),
        hovertemplate: "%{y:.3f} GHz · %{x:.1f} Oe<br>%{customdata[0]}<extra>Measured</extra>",
      },
    ],
    {
      ...plotLayout,
      xaxis: { ...plotLayout.xaxis, title: "Resonance field (Oe)" },
      yaxis: { ...plotLayout.yaxis, title: "Frequency (GHz)" },
    },
    plotConfig,
  );
}

function plotLinewidth(analysis) {
  const points = analysis.measurements;
  Plotly.react(
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
      xaxis: { ...plotLayout.xaxis, title: "Frequency (GHz)" },
      yaxis: { ...plotLayout.yaxis, title: "Peak-to-peak linewidth (Oe)" },
    },
    plotConfig,
  );
}

function showAnalysis(analysis) {
  const kittel = analysis.kittel_fit;
  const linewidth = analysis.linewidth_fit;
  document.querySelector("#sweep-count").textContent = String(analysis.measurements.length).padStart(2, "0");
  document.querySelector("#g-factor").textContent = kittel.g_factor.toFixed(4);
  document.querySelector("#perpendicular-field").textContent = kittel.effective_perpendicular_field_t.toFixed(4);
  document.querySelector("#fourfold-field").textContent = kittel.fourfold_field_t.toFixed(5);
  document.querySelector("#damping").textContent = linewidth.damping.toFixed(5);
  document.querySelector("#kittel-r2").textContent = `Kittel model R² ${kittel.r_squared.toFixed(5)}`;
  document.querySelector("#linewidth-r2").textContent = `Linewidth model R² ${linewidth.r_squared.toFixed(5)}`;
  document.querySelector("#kittel-equation").textContent = kittel.equation;
  document.querySelector("#linewidth-equation").textContent = linewidth.equation;
  plotKittel(analysis);
  plotLinewidth(analysis);
}

async function showTrace(measurementId) {
  const trace = await requestJson(`/api/measurements/${encodeURIComponent(measurementId)}`);
  Plotly.react(
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
        name: "Derivative-Lorentzian fit",
        line: { color: colors.cyan, width: 2 },
      },
    ],
    {
      ...plotLayout,
      xaxis: { ...plotLayout.xaxis, title: "Magnetic field (Oe)" },
      yaxis: { ...plotLayout.yaxis, title: "Lock-in signal (a.u.)" },
    },
    plotConfig,
  );
  document.querySelector("#trace-summary").textContent =
    `${trace.frequency_ghz.toFixed(3)} GHz  ·  Hres ${trace.resonance_field_oe.toFixed(2)} Oe  ·  ΔHpp ${trace.linewidth_pp_oe.toFixed(2)} Oe  ·  trace R² ${trace.r_squared.toFixed(5)}`;
  document.querySelector("#save-trace-button").dataset.filename =
    `fmr-trace-${trace.frequency_ghz.toFixed(3)}-GHz`;
}

async function analyze() {
  elements.error.hidden = true;
  elements.results.hidden = true;
  elements.loading.hidden = false;
  elements.button.disabled = true;
  try {
    const initialField = Number(elements.initialField.value);
    if (!Number.isFinite(initialField) || initialField < 0 || initialField > 2) {
      throw new Error("Initial perpendicular field must be between 0 and 2 T.");
    }
    const analysis = await requestJson(
      `/api/analysis?initial_perpendicular_field_t=${encodeURIComponent(initialField)}`,
    );
    measurements = analysis.measurements;
    elements.traceSelect.replaceChildren(
      ...measurements.map((measurement) => {
        const option = document.createElement("option");
        option.value = measurement.measurement_id;
        option.textContent = `${measurement.frequency_ghz.toFixed(3)} GHz`;
        return option;
      }),
    );
    showAnalysis(analysis);
    elements.results.hidden = false;
    await showTrace(elements.traceSelect.value);
  } catch (error) {
    displayError(error.message);
  } finally {
    elements.loading.hidden = true;
    elements.button.disabled = false;
  }
}

async function uploadDataset() {
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

  elements.uploadButton.disabled = true;
  elements.datasetStatus.textContent = `Uploading ${csvFiles.length} CSV files…`;
  try {
    const result = await requestJson("/api/datasets", { method: "POST", body: formData });
    elements.datasetStatus.textContent = `${result.measurement_count} uploaded CSV sweeps active`;
    await analyze();
  } catch (error) {
    elements.datasetStatus.textContent = "Upload rejected; the previous dataset is still active";
    displayError(error.message);
  } finally {
    elements.uploadButton.disabled = false;
  }
}

async function savePlot(chartId, filename) {
  try {
    await Plotly.downloadImage(chartId, {
      format: "png",
      filename,
      width: 1600,
      height: 1000,
      scale: 2,
    });
  } catch (error) {
    displayError(`Could not save plot: ${error.message}`);
  }
}

elements.button.addEventListener("click", analyze);
elements.uploadButton.addEventListener("click", () => elements.datasetFolder.click());
elements.datasetFolder.addEventListener("change", () => {
  const csvCount = Array.from(elements.datasetFolder.files).filter((file) =>
    file.name.toLowerCase().endsWith(".csv"),
  ).length;
  if (csvCount > 0) {
    uploadDataset();
  } else {
    elements.datasetStatus.textContent = "Bundled demo data loaded";
  }
});
document.querySelectorAll(".download-button").forEach((button) => {
  button.addEventListener("click", () => {
    savePlot(button.dataset.chart, button.dataset.filename);
  });
});
elements.traceSelect.addEventListener("change", () => {
  showTrace(elements.traceSelect.value).catch((error) => displayError(error.message));
});
analyze();
