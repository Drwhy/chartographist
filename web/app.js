const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const TILE_SIZE = 18;
const TERRAIN_COLORS = Object.freeze({
  ocean: "#16324f",
  deep_ocean: "#0d2238",
  coast: "#2f5d74",
  beach: "#b7a36a",
  desert: "#b89052",
  grassland: "#557a46",
  plains: "#6d8249",
  forest: "#28523a",
  rainforest: "#184331",
  swamp: "#354d3b",
  taiga: "#3c5f58",
  tundra: "#87938a",
  mountain: "#6f706b",
  snow: "#d7dfdc",
});

export function boundedZoom(value) {
  const numeric = Number(value);
  return Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number.isFinite(numeric) ? numeric : 1));
}

export function cellAtCanvasPoint(x, y, camera) {
  const scale = camera.tileSize * camera.zoom;
  return {
    x: Math.floor((x - camera.offsetX) / scale),
    y: Math.floor((y - camera.offsetY) / scale),
  };
}

export function applyDeltaToSnapshot(snapshot, delta, cellIndex = null) {
  if (!snapshot || delta.resync || snapshot.revision !== delta.from_revision) {
    return null;
  }
  if (cellIndex instanceof Map) {
    for (const cell of delta.cells || []) {
      cellIndex.set(`${cell.x},${cell.y}`, cell);
    }
    return {
      ...snapshot,
      revision: delta.to_revision,
      cycle: delta.cycle,
      clock: delta.clock || snapshot.clock,
      logs: delta.logs || snapshot.logs,
      panels: delta.panels || snapshot.panels,
      cells: snapshot.cells,
    };
  }
  const changes = new Map(
    (delta.cells || []).map((cell) => [`${cell.x},${cell.y}`, cell]),
  );
  return {
    ...snapshot,
    revision: delta.to_revision,
    cycle: delta.cycle,
    clock: delta.clock || snapshot.clock,
    logs: delta.logs || snapshot.logs,
    panels: delta.panels || snapshot.panels,
    cells: snapshot.cells.map((cell) => changes.get(`${cell.x},${cell.y}`) || cell),
  };
}

export function resolveSpriteLayers(cell) {
  const layers = ["terrain." + String(cell.terrain_key || "unknown")];
  if (cell.hydrology_key) {
    layers.push("hydrology." + cell.hydrology_key);
  }
  if (cell.infrastructure_key) {
    layers.push("infrastructure." + cell.infrastructure_key);
  }
  if (cell.site_key) {
    layers.push("site." + cell.site_key);
  }
  if (cell.entity?.render_key) {
    layers.push(cell.entity.render_key);
  }
  return layers;
}

export function resolveSprite(manifest, visualKey) {
  const parts = String(visualKey || "").split(".");
  while (parts.length) {
    const candidate = manifest.sprites[parts.join(".")];
    if (candidate) return candidate;
    parts.pop();
  }
  return manifest.sprites[manifest.fallback];
}

export function edgeBlendProfile(x, y, direction, depth = 0.18, steps = 8) {
  const count = Math.max(2, Math.min(16, Math.trunc(Number(steps)) || 8));
  const maximum = Math.max(0.01, Math.min(0.5, Number(depth) || 0.18));
  const directionSalt = direction === "left" ? 0x51ed270b : 0x2c1b3c6d;
  let seed = (
    Math.imul(Math.trunc(Number(x)) || 0, 0x165667b1)
    ^ Math.imul(Math.trunc(Number(y)) || 0, 0x27d4eb2d)
    ^ directionSalt
  ) >>> 0;
  const profile = [];
  for (let index = 0; index < count; index += 1) {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    const variation = 0.35 + ((seed >>> 0) % 651) / 1000;
    profile.push(Number((maximum * variation).toFixed(6)));
  }
  return profile;
}

function terrainColor(cell) {
  const key = String(cell.terrain_key || cell.visible_key || "").split(".").at(-1);
  if (cell.visible_key === "hydrology.river") return "#327da8";
  return TERRAIN_COLORS[key] || "#465044";
}

function startClient() {
  const canvas = document.getElementById("world-map");
  const context = canvas.getContext("2d", {alpha: false});
  const elements = {
    connection: document.getElementById("connection"),
    selection: document.getElementById("selection"),
    logs: document.getElementById("logs"),
    panel: document.getElementById("panel-content"),
    year: document.getElementById("year"),
    month: document.getElementById("month"),
    cycle: document.getElementById("cycle"),
    speed: document.getElementById("speed"),
    renderMode: document.getElementById("render-mode"),
  };
  const camera = {offsetX: 12, offsetY: 12, zoom: 1, tileSize: TILE_SIZE};
  const state = {
    labels: {},
    snapshot: null,
    cells: new Map(),
    selected: null,
    activePanel: "overview",
    socket: null,
    retry: 0,
    drawPending: false,
    dragging: false,
    moved: false,
    pointerX: 0,
    pointerY: 0,
    renderMode: "glyphs",
    tileset: null,
    tilesets: [],
  };

  function label(key) {
    return state.labels[key] || key;
  }

  function setConnection(kind) {
    elements.connection.dataset.state = kind;
    elements.connection.textContent = label(`connection_${kind}`);
  }

  function localize() {
    document.querySelectorAll("[data-i18n]").forEach((node) => {
      node.textContent = label(node.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
      node.setAttribute("aria-label", label(node.dataset.i18nAria));
    });
    if (!state.selected) elements.selection.textContent = label("no_selection");
  }

  function resizeCanvas() {
    const ratio = Math.max(1, Math.min(2, window.devicePixelRatio || 1));
    const bounds = canvas.getBoundingClientRect();
    const width = Math.max(1, Math.round(bounds.width * ratio));
    const height = Math.max(1, Math.round(bounds.height * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    context.setTransform(ratio, 0, 0, ratio, 0, 0);
    scheduleDraw();
  }

  function scheduleDraw() {
    if (state.drawPending) return;
    state.drawPending = true;
    requestAnimationFrame(draw);
  }

  function draw() {
    state.drawPending = false;
    const bounds = canvas.getBoundingClientRect();
    context.fillStyle = "#050705";
    context.fillRect(0, 0, bounds.width, bounds.height);
    if (!state.snapshot) return;
    const size = camera.tileSize * camera.zoom;
    const minX = Math.max(0, Math.floor(-camera.offsetX / size));
    const minY = Math.max(0, Math.floor(-camera.offsetY / size));
    const maxX = Math.min(
      state.snapshot.world?.width ?? Number.MAX_SAFE_INTEGER,
      Math.ceil((bounds.width - camera.offsetX) / size),
    );
    const maxY = Math.min(
      state.snapshot.world?.height ?? Number.MAX_SAFE_INTEGER,
      Math.ceil((bounds.height - camera.offsetY) / size),
    );
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.imageSmoothingEnabled = false;
    context.font = `${Math.max(7, Math.floor(size * 0.58))}px ui-monospace, monospace`;
    for (let y = minY; y < maxY; y += 1) {
      for (let x = minX; x < maxX; x += 1) {
        const cell = state.cells.get(`${x},${y}`);
        if (!cell) continue;
        const left = camera.offsetX + x * size;
        const top = camera.offsetY + y * size;
        context.fillStyle = terrainColor(cell);
        context.fillRect(left, top, Math.ceil(size), Math.ceil(size));
        if (state.tileset && state.renderMode !== "glyphs") {
          const manifest = state.tileset.manifest;
          const layers = resolveSpriteLayers(cell);
          const terrainSprite = resolveSprite(manifest, layers[0]);
          if (terrainSprite) drawSprite(terrainSprite, left, top, size);
          if (manifest.edge_blending?.mode === "interlaced") {
            drawTerrainEdge(
              cell,
              state.cells.get(`${x},${y - 1}`),
              "top",
              left,
              top,
              size,
            );
            drawTerrainEdge(
              cell,
              state.cells.get(`${x - 1},${y}`),
              "left",
              left,
              top,
              size,
            );
          }
          for (const visualKey of layers.slice(1)) {
            const sprite = resolveSprite(manifest, visualKey);
            if (!sprite) continue;
            drawSprite(sprite, left, top, size);
          }
        } else if (cell.entity || cell.site_key || cell.hydrology_key || cell.infrastructure_key) {
          context.fillStyle = "#f2ead3";
          context.fillText(String(cell.glyph || "?").trim().slice(0, 2), left + size / 2, top + size / 2);
        }
        if (state.selected?.x === x && state.selected?.y === y) {
          context.strokeStyle = "#f5cf62";
          context.lineWidth = 2;
          context.strokeRect(left + 1, top + 1, Math.max(1, size - 2), Math.max(1, size - 2));
        }
      }
    }
  }

  function drawSprite(sprite, left, top, size) {
    const manifest = state.tileset.manifest;
    context.drawImage(
      state.tileset.image,
      sprite.x * manifest.tile_width,
      sprite.y * manifest.tile_height,
      manifest.tile_width,
      manifest.tile_height,
      left,
      top,
      Math.ceil(size),
      Math.ceil(size),
    );
  }

  function drawTerrainEdge(cell, neighbor, direction, left, top, size) {
    if (!neighbor || neighbor.terrain_key === cell.terrain_key) return;
    const manifest = state.tileset.manifest;
    const sprite = resolveSprite(
      manifest,
      `terrain.${String(neighbor.terrain_key || "unknown")}`,
    );
    if (!sprite) return;
    const blending = manifest.edge_blending;
    const profile = edgeBlendProfile(
      cell.x,
      cell.y,
      direction,
      blending.depth,
      8,
    );
    context.save();
    context.beginPath();
    if (direction === "top") {
      context.moveTo(left, top);
      context.lineTo(left + size, top);
      for (let index = profile.length; index >= 0; index -= 1) {
        const depth = profile[Math.min(index, profile.length - 1)];
        context.lineTo(
          left + (index / profile.length) * size,
          top + depth * size,
        );
      }
    } else {
      context.moveTo(left, top);
      context.lineTo(left, top + size);
      for (let index = profile.length; index >= 0; index -= 1) {
        const depth = profile[Math.min(index, profile.length - 1)];
        context.lineTo(
          left + depth * size,
          top + (index / profile.length) * size,
        );
      }
    }
    context.closePath();
    context.clip();
    context.globalAlpha = blending.opacity;
    drawSprite(sprite, left, top, size);
    context.restore();
  }

  function rebuildCellIndex() {
    state.cells = new Map(
      (state.snapshot?.cells || []).map((cell) => [`${cell.x},${cell.y}`, cell]),
    );
  }

  function updateClock() {
    const clock = state.snapshot?.clock || {};
    elements.year.textContent = clock.year ?? "—";
    elements.month.textContent = clock.month ?? "—";
    elements.cycle.textContent = state.snapshot?.cycle ?? "—";
  }

  function renderLogs() {
    const fragment = document.createDocumentFragment();
    for (const value of (state.snapshot?.logs || []).slice(-40).reverse()) {
      const item = document.createElement("li");
      item.textContent = String(value);
      fragment.append(item);
    }
    elements.logs.replaceChildren(fragment);
  }

  function renderPanel() {
    const panels = state.snapshot?.panels || {};
    const value = state.activePanel === "overview" ? panels : panels[state.activePanel];
    elements.panel.textContent = JSON.stringify(value ?? {}, null, 2);
    document.querySelectorAll("[data-panel]").forEach((button) => {
      button.setAttribute("aria-selected", String(button.dataset.panel === state.activePanel));
    });
  }

  function renderSelection() {
    const cell = state.selected && state.cells.get(`${state.selected.x},${state.selected.y}`);
    elements.selection.replaceChildren();
    if (!cell) {
      elements.selection.textContent = label("no_selection");
      return;
    }
    const coordinates = document.createElement("strong");
    coordinates.textContent = `${cell.x}, ${cell.y}`;
    const terrain = document.createElement("div");
    terrain.textContent = `${label("terrain")}: ${cell.terrain_key || cell.visible_key}`;
    elements.selection.append(coordinates, terrain);
    if (cell.entity) {
      const entity = document.createElement("div");
      entity.textContent = `${label("entity")}: ${cell.entity.name || "#"+cell.entity.entity_id}`;
      elements.selection.append(entity);
    }
  }

  function consumeSnapshot(snapshot, center = false, rebuildCells = true) {
    state.snapshot = snapshot;
    if (rebuildCells) rebuildCellIndex();
    if (center && snapshot.world) {
      const bounds = canvas.getBoundingClientRect();
      const naturalWidth = snapshot.world.width * camera.tileSize;
      const naturalHeight = snapshot.world.height * camera.tileSize;
      camera.zoom = boundedZoom(Math.min(bounds.width / naturalWidth, bounds.height / naturalHeight));
      camera.offsetX = Math.round((bounds.width - naturalWidth * camera.zoom) / 2);
      camera.offsetY = Math.round((bounds.height - naturalHeight * camera.zoom) / 2);
    }
    updateClock();
    renderLogs();
    renderPanel();
    renderSelection();
    scheduleDraw();
  }

  async function refreshSnapshot(center = false) {
    const response = await fetch("/api/v1/snapshot", {cache: "no-store"});
    if (!response.ok) throw new Error(`snapshot ${response.status}`);
    consumeSnapshot(await response.json(), center);
  }

  function sendCommand(command, value) {
    const payload = value === undefined ? {command} : {command, value};
    if (state.socket?.readyState === WebSocket.OPEN) {
      state.socket.send(JSON.stringify(payload));
      return;
    }
    fetch("/api/v1/commands", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    }).catch(() => setConnection("disconnected"));
  }

  async function loadTileset(summary) {
    const response = await fetch(summary.manifest_url, {cache: "no-store"});
    if (!response.ok) throw new Error("tileset manifest");
    const manifest = await response.json();
    const image = new Image();
    image.decoding = "async";
    image.src = manifest.image_url;
    await image.decode();
    state.tileset = {manifest, image};
    state.renderMode = manifest.id;
    scheduleDraw();
  }

  function configureRenderModes(meta) {
    state.tilesets = meta.tilesets || [];
    elements.renderMode.replaceChildren();
    const glyphs = document.createElement("option");
    glyphs.value = "glyphs";
    glyphs.textContent = label("glyph_theme");
    elements.renderMode.append(glyphs);
    for (const summary of state.tilesets) {
      const option = document.createElement("option");
      option.value = summary.id;
      option.textContent = label("sprite_theme") + " · " + summary.name;
      elements.renderMode.append(option);
    }
    elements.renderMode.value = "glyphs";
  }

  function connect() {
    setConnection("connecting");
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${location.host}/api/v1/stream`);
    state.socket = socket;
    socket.addEventListener("open", () => {
      state.retry = 0;
      setConnection("connected");
    });
    socket.addEventListener("message", async (event) => {
      let message;
      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }
      if (message.type === "snapshot") {
        consumeSnapshot(message.payload, state.snapshot === null);
      } else if (message.type === "delta") {
        const next = applyDeltaToSnapshot(
          state.snapshot,
          message.payload,
          state.cells,
        );
        if (next) consumeSnapshot(next, false, false);
        else await refreshSnapshot();
      }
    });
    socket.addEventListener("close", () => {
      if (state.socket !== socket) return;
      setConnection("disconnected");
      const delay = Math.min(10000, 500 * (2 ** state.retry));
      state.retry += 1;
      window.setTimeout(connect, delay);
    });
    socket.addEventListener("error", () => socket.close());
  }

  function zoomAt(clientX, clientY, factor) {
    const bounds = canvas.getBoundingClientRect();
    const x = clientX - bounds.left;
    const y = clientY - bounds.top;
    const oldZoom = camera.zoom;
    const nextZoom = boundedZoom(oldZoom * factor);
    camera.offsetX = x - ((x - camera.offsetX) * nextZoom) / oldZoom;
    camera.offsetY = y - ((y - camera.offsetY) * nextZoom) / oldZoom;
    camera.zoom = nextZoom;
    scheduleDraw();
  }

  canvas.addEventListener("wheel", (event) => {
    event.preventDefault();
    zoomAt(event.clientX, event.clientY, event.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, {passive: false});

  canvas.addEventListener("pointerdown", (event) => {
    state.dragging = true;
    state.moved = false;
    state.pointerX = event.clientX;
    state.pointerY = event.clientY;
    canvas.classList.add("is-dragging");
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener("pointermove", (event) => {
    if (!state.dragging) return;
    const dx = event.clientX - state.pointerX;
    const dy = event.clientY - state.pointerY;
    state.moved ||= Math.abs(dx) + Math.abs(dy) > 2;
    camera.offsetX += dx;
    camera.offsetY += dy;
    state.pointerX = event.clientX;
    state.pointerY = event.clientY;
    scheduleDraw();
  });
  canvas.addEventListener("pointerup", (event) => {
    state.dragging = false;
    canvas.classList.remove("is-dragging");
    if (!state.moved) {
      const bounds = canvas.getBoundingClientRect();
      const cell = cellAtCanvasPoint(event.clientX - bounds.left, event.clientY - bounds.top, camera);
      if (state.cells.has(`${cell.x},${cell.y}`)) {
        state.selected = cell;
        renderSelection();
        scheduleDraw();
      }
    }
  });

  canvas.addEventListener("keydown", (event) => {
    const moves = {
      ArrowLeft: [24, 0],
      ArrowRight: [-24, 0],
      ArrowUp: [0, 24],
      ArrowDown: [0, -24],
    };
    if (moves[event.key]) {
      event.preventDefault();
      camera.offsetX += moves[event.key][0];
      camera.offsetY += moves[event.key][1];
      scheduleDraw();
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      const bounds = canvas.getBoundingClientRect();
      zoomAt(bounds.left + bounds.width / 2, bounds.top + bounds.height / 2, 1.15);
    } else if (event.key === "-") {
      event.preventDefault();
      const bounds = canvas.getBoundingClientRect();
      zoomAt(bounds.left + bounds.width / 2, bounds.top + bounds.height / 2, 1 / 1.15);
    } else if (event.key === " ") {
      event.preventDefault();
      sendCommand("pause");
    } else if (event.key === ".") {
      event.preventDefault();
      sendCommand("step");
    }
  });

  document.getElementById("pause").addEventListener("click", () => sendCommand("pause"));
  document.getElementById("resume").addEventListener("click", () => sendCommand("resume"));
  document.getElementById("step").addEventListener("click", () => sendCommand("step"));
  elements.speed.addEventListener("change", () => sendCommand("speed", Number(elements.speed.value)));
  elements.renderMode.addEventListener("change", async () => {
    const identifier = elements.renderMode.value;
    if (identifier === "glyphs") {
      state.renderMode = "glyphs";
      state.tileset = null;
      scheduleDraw();
      return;
    }
    const summary = state.tilesets.find((item) => item.id === identifier);
    if (!summary) {
      elements.renderMode.value = "glyphs";
      return;
    }
    try {
      await loadTileset(summary);
    } catch {
      state.renderMode = "glyphs";
      state.tileset = null;
      elements.renderMode.value = "glyphs";
      scheduleDraw();
    }
  });
  document.querySelectorAll("[data-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activePanel = button.dataset.panel;
      renderPanel();
    });
  });

  new ResizeObserver(resizeCanvas).observe(canvas);
  fetch("/api/v1/meta", {cache: "no-store"})
    .then((response) => response.ok ? response.json() : Promise.reject(new Error("meta")))
    .then((meta) => {
      state.labels = meta.labels || {};
      document.documentElement.lang = meta.language || "fr";
      elements.speed.value = String(meta.runtime?.tick_interval ?? 0.15);
      localize();
      configureRenderModes(meta);
      connect();
    })
    .catch(() => setConnection("disconnected"));
  resizeCanvas();
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", startClient);
}
