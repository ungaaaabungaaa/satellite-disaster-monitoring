import { classifyIndices } from "./classification.mjs";

const element = (id) => document.getElementById(id);
const status = element("status");
const canvas = element("map"),
  context = canvas.getContext("2d");
const state = { mode: "split", divider: 50, threshold: 0, shade: true };
let study, before, after, beforeImage, afterImage, classified;

async function collect(stream, limit) {
  const reader = stream.getReader(),
    parts = [];
  let length = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > limit) {
      await reader.cancel();
      throw new Error("Study asset exceeds its size bound.");
    }
    parts.push(value);
  }
  const result = new Uint8Array(length);
  let offset = 0;
  for (const part of parts) {
    result.set(part, offset);
    offset += part.length;
  }
  return result;
}

async function asset(name) {
  const response = await fetch(`./${name}`);
  if (!response.ok) throw new Error(`Cannot load ${name}.`);
  const bytes = await collect(response.body, 16_000_000);
  const hash = [...new Uint8Array(await crypto.subtle.digest("SHA-256", bytes))]
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
  if (hash !== study.asset_sha256[name])
    throw new Error(`Integrity check failed for ${name}.`);
  return bytes;
}

async function indices(name) {
  const bytes = await asset(name);
  const stream = new Blob([bytes])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"));
  const raw = await collect(stream, study.width * study.height * 4);
  if (raw.length !== study.width * study.height * 4)
    throw new Error("Index dimensions do not match.");
  const view = new DataView(raw.buffer),
    result = new Float32Array(study.width * study.height);
  for (let i = 0; i < result.length; i++)
    result[i] = view.getFloat32(i * 4, true);
  return result;
}

async function image(name) {
  const bytes = await asset(name),
    url = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
  try {
    const result = new Image();
    result.src = url;
    await result.decode();
    if (result.width !== study.width || result.height !== study.height)
      throw new Error("Image grid mismatch.");
    return result;
  } finally {
    URL.revokeObjectURL(url);
  }
}

function recompute() {
  classified = classifyIndices(before, after, state.threshold);
  const recorded = study.thresholds.find(
    (item) => item.threshold === state.threshold,
  );
  for (const [js, python] of [
    ["common", "common_valid_pixels"],
    ["before", "before_water_pixels"],
    ["after", "after_water_pixels"],
    ["gain", "gain_pixels"],
    ["loss", "loss_pixels"],
  ]) {
    if (!recorded || classified.counts[js] !== recorded[python])
      throw new Error("Browser counts differ from the Python report.");
  }
  const area = recorded.pixel_area_m2 / 1_000_000,
    counts = classified.counts;
  const format = (value) => (value * area).toFixed(2);
  element("common-area").textContent = format(counts.common);
  element("coverage-detail").textContent =
    `${((100 * counts.common) / before.length).toFixed(1)}% of the grid · ${counts.common.toLocaleString()} pixels valid on both dates`;
  for (const key of ["before", "after", "gain", "loss"])
    element(`${key}-area`).textContent = format(counts[key]);
}

function render() {
  const width = study.width,
    height = study.height,
    split = Math.floor((width * state.divider) / 100);
  context.clearRect(0, 0, width, height);
  if (state.mode === "split") {
    context.drawImage(afterImage, 0, 0);
    context.save();
    context.beginPath();
    context.rect(0, 0, split, height);
    context.clip();
    context.drawImage(beforeImage, 0, 0);
    context.restore();
  } else
    context.drawImage(state.mode === "before" ? beforeImage : afterImage, 0, 0);
  const overlay = context.createImageData(width, height);
  const colors = { 2: [57, 94, 118], 3: [28, 160, 168], 4: [189, 124, 61] };
  for (let i = 0; i < classified.classes.length; i++) {
    const code = classified.classes[i],
      offset = i * 4;
    if (code === 0 && state.shade) {
      overlay.data.set([211, 217, 211, 230], offset);
    } else if (state.mode === "change" && code >= 2) {
      overlay.data.set([...colors[code], 210], offset);
    }
  }
  const layer = document.createElement("canvas");
  layer.width = width;
  layer.height = height;
  layer.getContext("2d").putImageData(overlay, 0, 0);
  context.drawImage(layer, 0, 0);
  if (state.mode === "split") {
    context.strokeStyle = "#f2f1eb";
    context.lineWidth = Math.max(1, width / 350);
    context.beginPath();
    context.moveTo(split, 0);
    context.lineTo(split, height);
    context.stroke();
  }
  for (const button of document.querySelectorAll("[data-mode]"))
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.mode === state.mode),
    );
  element("divider").disabled = state.mode !== "split";
  element("before-date").hidden = state.mode === "after";
  element("after-date").hidden = state.mode === "before";
  for (const entry of document.querySelectorAll(".legend span")) {
    if (!entry.querySelector(".excluded"))
      entry.style.display = state.mode === "change" ? "flex" : "none";
  }
}

function fail(error) {
  status.classList.add("error");
  status.textContent = error.message;
}

async function start() {
  const response = await fetch("./data.json");
  if (!response.ok)
    throw new Error(
      "Cannot load the local study. Use the loopback preview server.",
    );
  const metadata = await collect(response.body, 1_000_000);
  study = JSON.parse(new TextDecoder().decode(metadata));
  if (
    study.schema_version !== 1 ||
    !Number.isInteger(study.width) ||
    !Number.isInteger(study.height) ||
    study.width < 1 ||
    study.height < 1 ||
    Math.max(study.width, study.height) > 2000 ||
    study.width * study.height > 2_000_000 ||
    !study.transform.every(Number.isFinite)
  )
    throw new Error("Invalid study metadata.");
  [before, after, beforeImage, afterImage] = await Promise.all([
    indices("before.f32.gz"),
    indices("after.f32.gz"),
    image("before.png"),
    image("after.png"),
  ]);
  canvas.width = study.width;
  canvas.height = study.height;
  element("before-date").textContent =
    `BEFORE · ${study.acquisition_utc[0].slice(0, 10)}`;
  element("after-date").textContent =
    `AFTER · ${study.acquisition_utc[1].slice(0, 10)}`;
  const pinned = study.study_status === "pinned-historical-study";
  element("study-location").textContent = pinned
    ? "JAMUNA RIVER · BANGLADESH · SENTINEL-2B"
    : "CUSTOM LOCAL STUDY · UNVERIFIED SOURCE";
  element("historical-context").hidden = !pinned;
  if (!pinned)
    element("processing-description").textContent =
      "Dates, reflectance conventions, and display RGB bands come from the supplied GeoTIFF metadata. Their source is unverified. Both images are aligned to the displayed projected grid; the footprint download supplies WGS84 geography.";
  const barPixels = Math.max(1, Math.min(100, Math.floor(study.width / 4)));
  const barMeters = barPixels * Math.abs(study.transform[0]);
  element("scale-graphic").style.width = `${(100 * barPixels) / study.width}%`;
  element("scale-graphic").textContent =
    barMeters >= 1000 ? `${barMeters / 1000} km` : `${barMeters} m`;
  element("source-ids").textContent =
    `${study.source_ids.join(" / ")} · ${study.crs}`;
  element("grid-label").textContent =
    `${Math.abs(study.transform[0]).toFixed(0)} m grid · ${study.crs}`;
  element("scale-label").textContent =
    `${study.width.toLocaleString()} × ${study.height.toLocaleString()} pixels`;
  for (const control of document.querySelectorAll("button,input,select"))
    control.disabled = false;
  recompute();
  render();
  status.textContent = `${study.study_status} · displayed assets verified · dates from image metadata`;
  for (const button of document.querySelectorAll("[data-mode]"))
    button.addEventListener("click", () => {
      state.mode = button.dataset.mode;
      render();
    });
  element("divider").addEventListener("input", (event) => {
    state.divider = Number(event.target.value);
    render();
  });
  element("threshold").addEventListener("change", (event) => {
    try {
      state.threshold = Number(event.target.value);
      recompute();
      render();
    } catch (error) {
      fail(error);
    }
  });
  element("quality").addEventListener("change", (event) => {
    state.shade = event.target.checked;
    render();
  });
  canvas.addEventListener("pointermove", (event) => {
    const rect = canvas.getBoundingClientRect();
    const x = Math.max(
      0,
      Math.min(
        study.width - 1,
        Math.floor(((event.clientX - rect.left) / rect.width) * study.width),
      ),
    );
    const y = Math.max(
      0,
      Math.min(
        study.height - 1,
        Math.floor(((event.clientY - rect.top) / rect.height) * study.height),
      ),
    );
    const t = study.transform,
      east = t[0] * (x + 0.5) + t[1] * (y + 0.5) + t[2],
      north = t[3] * (x + 0.5) + t[4] * (y + 0.5) + t[5];
    const index = y * study.width + x;
    const value =
      Number.isFinite(before[index]) && Number.isFinite(after[index])
        ? `MNDWI ${before[index].toFixed(3)} → ${after[index].toFixed(3)}`
        : "excluded from the common footprint";
    element("coordinate").textContent =
      `E ${east.toFixed(0)} · N ${north.toFixed(0)} m · ${value}`;
  });
}
start().catch(fail);
