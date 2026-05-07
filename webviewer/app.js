const state = {
  payload: null,
  desktop: null,
  modeIndex: 0,
  fieldKey: "normE",
  view: "desktop",
  busy: false,
};

const modelName = document.getElementById("model-name");
const serverTarget = document.getElementById("server-target");
const desktopRunning = document.getElementById("desktop-running");
const modelPathInput = document.getElementById("model-path-input");
const openModelButton = document.getElementById("open-model-button");
const loadedModels = document.getElementById("loaded-models");
const parameterForm = document.getElementById("parameter-form");
const plotList = document.getElementById("plot-list");
const viewTabs = document.getElementById("view-tabs");
const modeTabs = document.getElementById("mode-tabs");
const fieldTabs = document.getElementById("field-tabs");
const modeGroup = document.getElementById("mode-group");
const fieldGroup = document.getElementById("field-group");
const statusText = document.getElementById("status-text");
const canvas = document.getElementById("field-canvas");
const legendCanvas = document.getElementById("legend-canvas");
const previewView = document.getElementById("preview-view");
const previewReady = document.getElementById("preview-ready");
const previewEmpty = document.getElementById("preview-empty");
const previewEmptyText = document.getElementById("preview-empty-text");
const desktopView = document.getElementById("desktop-view");
const desktopImage = document.getElementById("desktop-image");
const desktopStatus = document.getElementById("desktop-status");
const desktopCaption = document.getElementById("desktop-caption");
const desktopRefreshButton = document.getElementById("desktop-refresh-button");
const modeValue = document.getElementById("mode-value");
const fieldMin = document.getElementById("field-min");
const fieldMax = document.getElementById("field-max");
const pointCount = document.getElementById("point-count");
const refreshButton = document.getElementById("refresh-button");
const solveButton = document.getElementById("solve-button");
const legendLabels = document.getElementById("legend-labels");
let desktopRefreshTimer = null;

function setBusy(busy, message) {
  state.busy = busy;
  refreshButton.disabled = busy;
  solveButton.disabled = busy;
  openModelButton.disabled = busy;
  desktopRefreshButton.disabled = busy;
  statusText.textContent = message;
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) {
    return "-";
  }
  const absolute = Math.abs(number);
  if (absolute >= 1.0e4 || (absolute > 0 && absolute < 1.0e-3)) {
    return number.toExponential(3);
  }
  return number.toFixed(4);
}

function magnitudeColor(t) {
  const clamped = Math.min(Math.max(t, 0), 1);
  const hue = (1 - clamped) * 240;
  return `hsl(${hue}, 95%, 56%)`;
}

function signedColor(t) {
  const clamped = Math.min(Math.max(t, 0), 1);
  const hue = clamped < 0.5 ? 215 : 8;
  const light = clamped < 0.5 ? 72 - clamped * 44 : 50 + (clamped - 0.5) * 44;
  return `hsl(${hue}, 78%, ${light}%)`;
}

function colorForValue(value, stats, mode) {
  const min = Number(stats?.min ?? 0);
  const max = Number(stats?.max ?? 1);
  if (mode === "signed") {
    const edge = Math.max(Math.abs(min), Math.abs(max), 1.0e-12);
    return signedColor((value + edge) / (edge * 2));
  }
  const span = Math.max(max - min, 1.0e-12);
  return magnitudeColor((value - min) / span);
}

function currentPreview() {
  return state.payload?.preview?.available ? state.payload.preview : null;
}

function renderViewTabs() {
  viewTabs.innerHTML = "";
  [
    { key: "desktop", label: "Desktop" },
    { key: "preview", label: "Preview" },
  ].forEach((view) => {
    const button = document.createElement("button");
    button.className = `segment-button${view.key === state.view ? " active" : ""}`;
    button.textContent = view.label;
    button.addEventListener("click", () => activateView(view.key));
    viewTabs.appendChild(button);
  });
}

function drawLegend(fieldSpec, stats) {
  const context = legendCanvas.getContext("2d");
  const width = legendCanvas.width;
  const height = legendCanvas.height;
  context.clearRect(0, 0, width, height);
  for (let row = 0; row < height; row += 1) {
    const ratio = 1 - row / (height - 1);
    const value = fieldSpec.mode === "signed"
      ? (ratio * 2 - 1) * Math.max(Math.abs(stats.min), Math.abs(stats.max), 1.0e-12)
      : stats.min + ratio * (stats.max - stats.min);
    context.fillStyle = colorForValue(value, stats, fieldSpec.mode);
    context.fillRect(0, row, width, 1);
  }
  legendLabels.innerHTML = "";
  [stats.max, (stats.max + stats.min) / 2, stats.min].forEach((value) => {
    const item = document.createElement("div");
    item.textContent = formatNumber(value);
    legendLabels.appendChild(item);
  });
}

function renderSession() {
  const payload = state.payload;
  const host = payload?.server?.host || "localhost";
  const port = payload?.server?.port ?? "-";
  serverTarget.textContent = `${host}:${port}`;
  desktopRunning.textContent = payload?.session?.desktopRunning ? "Visible" : "Not visible";
  modelName.textContent = payload?.model?.name || "COMSOL Desktop Bridge";
  if (!modelPathInput.value && payload?.model?.file) {
    modelPathInput.value = payload.model.file;
  }
}

function renderLoadedModels() {
  loadedModels.innerHTML = "";
  const models = state.payload?.session?.loadedModels || [];
  if (!models.length) {
    const empty = document.createElement("div");
    empty.className = "list-empty";
    empty.textContent = "No model loaded yet.";
    loadedModels.appendChild(empty);
    return;
  }
  models.forEach((model) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = `model-card${model.name === state.payload.session.activeModel ? " active" : ""}`;
    item.addEventListener("click", () => activateModel(model.name));
    const title = document.createElement("strong");
    title.textContent = model.name;
    const meta = document.createElement("span");
    meta.textContent = model.sourcePath || model.file;
    item.appendChild(title);
    item.appendChild(meta);
    loadedModels.appendChild(item);
  });
}

function renderParameters() {
  const parameters = state.payload?.model?.parameters || {};
  parameterForm.innerHTML = "";
  const entries = Object.entries(parameters);
  if (!entries.length) {
    const empty = document.createElement("div");
    empty.className = "list-empty";
    empty.textContent = "Load a model to expose its parameters here.";
    parameterForm.appendChild(empty);
    return;
  }
  entries.forEach(([name, value]) => {
    const wrapper = document.createElement("div");
    wrapper.className = "parameter-item";
    const label = document.createElement("label");
    label.setAttribute("for", `param-${name}`);
    label.textContent = name;
    const input = document.createElement("input");
    input.id = `param-${name}`;
    input.name = name;
    input.value = value;
    wrapper.appendChild(label);
    wrapper.appendChild(input);
    parameterForm.appendChild(wrapper);
  });
}

function previewFieldKey(plot) {
  const preview = currentPreview();
  if (!preview) {
    return state.fieldKey;
  }
  const name = String(plot?.name || "").toLowerCase();
  if (name.includes("transverse") && preview.fieldSpecs.reEy) {
    return "reEy";
  }
  if (name.includes("electric") && preview.fieldSpecs.normE) {
    return "normE";
  }
  return Object.keys(preview.fieldSpecs)[0];
}

function drawFieldPreview(previewCanvas, fieldKey) {
  const preview = currentPreview();
  if (!preview) {
    return;
  }
  const solution = preview.solutions[state.modeIndex];
  const fieldSpec = preview.fieldSpecs[fieldKey];
  const field = solution.fields[fieldKey];
  const xValues = preview.geometry.xUm;
  const yValues = preview.geometry.yUm;
  const stats = field.stats;
  const bounds = preview.geometry.boundsUm;
  const context = previewCanvas.getContext("2d");
  const width = previewCanvas.width;
  const height = previewCanvas.height;

  context.clearRect(0, 0, width, height);
  context.fillStyle = "#0f1720";
  context.fillRect(0, 0, width, height);

  const padding = 12;
  const plotWidth = width - padding * 2;
  const plotHeight = height - padding * 2;
  const xSpan = Math.max(bounds.xMax - bounds.xMin, 1.0e-9);
  const ySpan = Math.max(bounds.yMax - bounds.yMin, 1.0e-9);
  const pointSize = Math.max(1, Math.round(Math.min(plotWidth, plotHeight) / 120));

  for (let index = 0; index < field.values.length; index += 1) {
    const x = xValues[index];
    const y = yValues[index];
    const px = padding + ((x - bounds.xMin) / xSpan) * plotWidth;
    const py = height - padding - ((y - bounds.yMin) / ySpan) * plotHeight;
    context.fillStyle = colorForValue(field.values[index], stats, fieldSpec.mode);
    context.fillRect(px - pointSize / 2, py - pointSize / 2, pointSize, pointSize);
  }

  context.strokeStyle = "rgba(226, 232, 240, 0.45)";
  context.lineWidth = 1;
  context.strokeRect(padding, padding, plotWidth, plotHeight);
}

function renderPlots() {
  plotList.innerHTML = "";
  const preview = currentPreview();
  if (!preview || !preview.plots?.length) {
    const empty = document.createElement("div");
    empty.className = "list-empty";
    empty.textContent = "No generic preview channel is available for the current model.";
    plotList.appendChild(empty);
    return;
  }
  preview.plots.forEach((plot) => {
    const fieldKey = previewFieldKey(plot);
    const item = document.createElement("button");
    item.type = "button";
    item.className = `plot-card${fieldKey === state.fieldKey ? " active" : ""}`;
    item.addEventListener("click", () => {
      state.fieldKey = fieldKey;
      render();
    });
    const image = document.createElement("canvas");
    image.className = "plot-thumb";
    image.width = 240;
    image.height = 188;
    const label = document.createElement("span");
    label.textContent = plot.name;
    const meta = document.createElement("small");
    meta.textContent = preview.fieldSpecs[fieldKey]?.label || fieldKey;
    item.appendChild(image);
    item.appendChild(label);
    item.appendChild(meta);
    plotList.appendChild(item);
    drawFieldPreview(image, fieldKey);
  });
}

function renderModeTabs() {
  const preview = currentPreview();
  modeTabs.innerHTML = "";
  if (!preview) {
    return;
  }
  preview.solutions.forEach((solution, index) => {
    const button = document.createElement("button");
    button.className = `segment-button${index === state.modeIndex ? " active" : ""}`;
    button.textContent = `Mode ${solution.modeIndex}`;
    button.addEventListener("click", () => {
      state.modeIndex = index;
      render();
    });
    modeTabs.appendChild(button);
  });
}

function renderFieldTabs() {
  const preview = currentPreview();
  fieldTabs.innerHTML = "";
  if (!preview) {
    return;
  }
  Object.entries(preview.fieldSpecs).forEach(([key, spec]) => {
    const button = document.createElement("button");
    button.className = `segment-button${key === state.fieldKey ? " active" : ""}`;
    button.textContent = spec.label;
    button.addEventListener("click", () => {
      state.fieldKey = key;
      render();
    });
    fieldTabs.appendChild(button);
  });
}

function renderCanvas() {
  const preview = currentPreview();
  if (!preview) {
    return;
  }
  const solution = preview.solutions[state.modeIndex];
  const fieldSpec = preview.fieldSpecs[state.fieldKey];
  const field = solution.fields[state.fieldKey];
  const xValues = preview.geometry.xUm;
  const yValues = preview.geometry.yUm;
  const stats = field.stats;
  const bounds = preview.geometry.boundsUm;

  const rect = canvas.getBoundingClientRect();
  const pixelRatio = window.devicePixelRatio || 1;
  canvas.width = Math.max(640, Math.floor(rect.width * pixelRatio));
  canvas.height = Math.max(480, Math.floor(rect.height * pixelRatio));

  const context = canvas.getContext("2d");
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = "#0f1720";
  context.fillRect(0, 0, canvas.width, canvas.height);

  const padding = 40 * pixelRatio;
  const plotWidth = canvas.width - padding * 2;
  const plotHeight = canvas.height - padding * 2;
  const xSpan = Math.max(bounds.xMax - bounds.xMin, 1.0e-9);
  const ySpan = Math.max(bounds.yMax - bounds.yMin, 1.0e-9);
  const pointSize = Math.max(2, Math.round(Math.min(plotWidth, plotHeight) / 220));

  for (let index = 0; index < field.values.length; index += 1) {
    const x = xValues[index];
    const y = yValues[index];
    const px = padding + ((x - bounds.xMin) / xSpan) * plotWidth;
    const py = canvas.height - padding - ((y - bounds.yMin) / ySpan) * plotHeight;
    context.fillStyle = colorForValue(field.values[index], stats, fieldSpec.mode);
    context.fillRect(px - pointSize / 2, py - pointSize / 2, pointSize, pointSize);
  }

  context.strokeStyle = "rgba(226, 232, 240, 0.8)";
  context.lineWidth = 1.5 * pixelRatio;
  context.strokeRect(padding, padding, plotWidth, plotHeight);

  context.fillStyle = "rgba(226, 232, 240, 0.9)";
  context.font = `${12 * pixelRatio}px Segoe UI`;
  context.fillText(`x (${String.fromCharCode(181)}m)`, canvas.width / 2 - 18 * pixelRatio, canvas.height - 10 * pixelRatio);
  context.save();
  context.translate(14 * pixelRatio, canvas.height / 2 + 20 * pixelRatio);
  context.rotate(-Math.PI / 2);
  context.fillText(`y (${String.fromCharCode(181)}m)`, 0, 0);
  context.restore();

  drawLegend(fieldSpec, stats);
  modeValue.textContent = formatNumber(solution.modeValue);
  fieldMin.textContent = formatNumber(stats.min);
  fieldMax.textContent = formatNumber(stats.max);
  pointCount.textContent = `${field.values.length}`;
}

function renderPreviewState() {
  const preview = currentPreview();
  const ready = Boolean(preview);
  previewReady.classList.toggle("hidden", !ready);
  previewEmpty.classList.toggle("hidden", ready);
  modeGroup.classList.toggle("hidden", !ready);
  fieldGroup.classList.toggle("hidden", !ready);
  if (!ready) {
    previewEmptyText.textContent = state.payload?.preview?.reason || "Desktop view is the generic path for any COMSOL model.";
    modeValue.textContent = "-";
    fieldMin.textContent = "-";
    fieldMax.textContent = "-";
    pointCount.textContent = "-";
    legendLabels.innerHTML = "";
    const context = legendCanvas.getContext("2d");
    context.clearRect(0, 0, legendCanvas.width, legendCanvas.height);
  }
}

function renderDesktop() {
  if (!state.desktop) {
    desktopStatus.textContent = "Waiting for COMSOL Desktop...";
    desktopCaption.textContent = "-";
    desktopImage.removeAttribute("src");
    return;
  }
  if (!state.desktop.available) {
    desktopStatus.textContent = state.desktop.error || "COMSOL Desktop is not available.";
    desktopCaption.textContent = "Open COMSOL Desktop and refresh this panel.";
    desktopImage.removeAttribute("src");
    return;
  }
  desktopStatus.textContent = state.desktop.title || "COMSOL Desktop";
  desktopCaption.textContent = `Captured ${state.desktop.capturedAt} · ${state.desktop.width} × ${state.desktop.height}`;
  desktopImage.src = `${state.desktop.imagePath}?t=${Date.now()}`;
}

function syncViewPanels() {
  previewView.classList.toggle("hidden", state.view !== "preview");
  desktopView.classList.toggle("hidden", state.view !== "desktop");
}

function render() {
  renderSession();
  renderLoadedModels();
  renderParameters();
  renderViewTabs();
  renderPreviewState();
  renderModeTabs();
  renderFieldTabs();
  renderPlots();
  renderDesktop();
  syncViewPanels();
  if (currentPreview()) {
    renderCanvas();
  }
}

async function fetchDesktopStatus({ refresh = true, quiet = false } = {}) {
  if (!quiet) {
    desktopStatus.textContent = "Capturing COMSOL Desktop...";
  }
  try {
    const response = await fetch(`/api/desktop/status?refresh=${refresh ? "1" : "0"}`, {
      cache: "no-store",
    });
    const payload = await response.json();
    state.desktop = payload;
    renderDesktop();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to capture COMSOL Desktop.");
    }
  } catch (error) {
    state.desktop = {
      available: false,
      error: String(error.message || error),
    };
    renderDesktop();
  }
}

async function fetchStatus() {
  setBusy(true, "Loading COMSOL workspace...");
  try {
    const response = await fetch("/api/status", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Failed to load COMSOL workspace.");
    }
    state.payload = payload;
    state.modeIndex = 0;
    state.fieldKey = "normE";
    render();
    setBusy(false, `Updated ${payload.generatedAt}`);
  } catch (error) {
    setBusy(false, String(error.message || error));
  }
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request failed.");
  }
  state.payload = payload;
  render();
  statusText.textContent = `Updated ${payload.generatedAt}`;
}

function activateView(viewKey) {
  state.view = viewKey;
  syncViewPanels();
  renderViewTabs();
  if (desktopRefreshTimer) {
    window.clearInterval(desktopRefreshTimer);
    desktopRefreshTimer = null;
  }
  if (viewKey === "desktop") {
    fetchDesktopStatus({ refresh: true, quiet: false });
    desktopRefreshTimer = window.setInterval(() => {
      fetchDesktopStatus({ refresh: true, quiet: true });
    }, 3000);
  }
}

function collectParameters() {
  const data = {};
  new FormData(parameterForm).forEach((value, key) => {
    data[key] = String(value);
  });
  return data;
}

async function runStudy({ solve }) {
  if (!state.payload?.model) {
    statusText.textContent = "Open a model first.";
    return;
  }
  setBusy(true, solve ? "Running COMSOL study..." : "Applying parameters...");
  try {
    await postJson("/api/run", {
      solve,
      parameters: collectParameters(),
    });
  } catch (error) {
    statusText.textContent = String(error.message || error);
  } finally {
    setBusy(false, statusText.textContent);
  }
}

async function openModel() {
  const path = modelPathInput.value.trim();
  if (!path) {
    statusText.textContent = "Enter a .mph path first.";
    return;
  }
  setBusy(true, "Opening COMSOL model...");
  try {
    await postJson("/api/model/open", { path });
  } catch (error) {
    statusText.textContent = String(error.message || error);
  } finally {
    setBusy(false, statusText.textContent);
  }
}

async function activateModel(model) {
  setBusy(true, `Switching to ${model}...`);
  try {
    await postJson("/api/model/activate", { model });
  } catch (error) {
    statusText.textContent = String(error.message || error);
  } finally {
    setBusy(false, statusText.textContent);
  }
}

refreshButton.addEventListener("click", () => fetchStatus());
solveButton.addEventListener("click", () => runStudy({ solve: true }));
openModelButton.addEventListener("click", openModel);
desktopRefreshButton.addEventListener("click", () => fetchDesktopStatus({ refresh: true, quiet: false }));
window.addEventListener("resize", () => {
  if (currentPreview()) {
    renderCanvas();
  }
});

fetchStatus().then(() => {
  activateView("desktop");
});
