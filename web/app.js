const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const TILE_SIZE = 18;
const ENTITY_FRAME_MS = 125;
const ENTITY_MOTION_MS = 375;
const MAX_ENTITY_FRAMES = 8;
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

export function archiveRevisionStep(value, minimum, maximum, delta) {
  const lower = Math.trunc(Number(minimum));
  const upper = Math.max(lower, Math.trunc(Number(maximum)));
  const current = Math.trunc(Number(value));
  const step = Math.trunc(Number(delta));
  return Math.max(lower, Math.min(upper, current + step));
}

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

export function panelForView(panels, activePanel) {
  const safePanels = panels && typeof panels === "object" ? panels : {};
  if (activePanel === "overview") return safePanels.metrics || {};
  return safePanels[activePanel] || {};
}

export function entitySpriteCandidates(entity, motion = "idle", frame = 0) {
  const base = String(entity?.render_key || "");
  const direction = String(entity?.direction || "south");
  const state = motion === "moving" ? "moving" : "idle";
  const index = Math.max(0, Math.trunc(Number(frame) || 0));
  return [
    `${base}.${direction}.${state}.frame_${index}`,
    `${base}.${direction}.${state}.frame_0`,
    `${base}.${direction}`,
    base,
  ];
}

export function animationFrameIndex(elapsedMs, frameCount, reducedMotion = false) {
  const count = Math.max(0, Math.min(MAX_ENTITY_FRAMES, Math.trunc(Number(frameCount))));
  if (reducedMotion || count <= 1) return 0;
  return Math.floor(Math.max(0, Number(elapsedMs) || 0) / ENTITY_FRAME_MS) % count;
}

export function movingEntityIds(previousCells, currentCells) {
  const positions = (cells) => new Map(
    (cells || [])
      .filter((cell) => cell?.entity?.entity_id !== undefined)
      .map((cell) => [Number(cell.entity.entity_id), `${cell.x},${cell.y}`]),
  );
  const previous = positions(previousCells);
  const current = positions(currentCells);
  return new Set(
    [...current].filter(([identifier, position]) => (
      previous.has(identifier) && previous.get(identifier) !== position
    )).map(([identifier]) => identifier),
  );
}

export function createCanvasPerformanceTracker(sampleLimit = 600) {
  const limit = Math.max(1, Math.min(3600, Math.trunc(Number(sampleLimit)) || 600));
  const maximumActiveInterval = 250;
  let previousTimestamp = null;
  const samples = [];
  const rounded = (value) => Number(value.toFixed(3));
  const percentile = (values, ratio) => {
    if (!values.length) return 0;
    const sorted = [...values].sort((left, right) => left - right);
    const index = Math.max(0, Math.ceil(sorted.length * ratio) - 1);
    return rounded(sorted[index]);
  };
  return {
    record(timestamp, drawMs, visibleCells) {
      const current = Number(timestamp);
      const interval = previousTimestamp === null ? null : current - previousTimestamp;
      previousTimestamp = current;
      samples.push({
        interval_ms: Number.isFinite(interval) && interval > 0 ? interval : null,
        draw_ms: Math.max(0, Number(drawMs) || 0),
        visible_cells: Math.max(0, Math.trunc(Number(visibleCells)) || 0),
      });
      if (samples.length > limit) samples.shift();
    },
    reset() {
      samples.length = 0;
      previousTimestamp = null;
    },
    report() {
      const intervals = samples
        .map((sample) => sample.interval_ms)
        .filter((value) => value !== null && value <= maximumActiveInterval);
      const draws = samples.map((sample) => sample.draw_ms);
      const meanInterval = intervals.length
        ? intervals.reduce((total, value) => total + value, 0) / intervals.length
        : 0;
      return {
        frames: samples.length,
        fps: meanInterval ? rounded(1000 / meanInterval) : 0,
        interval_ms: {
          median: percentile(intervals, 0.5),
          p95: percentile(intervals, 0.95),
          max: percentile(intervals, 1),
        },
        draw_ms: {
          median: percentile(draws, 0.5),
          p95: percentile(draws, 0.95),
          max: percentile(draws, 1),
        },
        visible_cells: samples.reduce(
          (maximum, sample) => Math.max(maximum, sample.visible_cells),
          0,
        ),
      };
    },
  };
}

export function runCanvasBenchmark(scheduleDraw, tracker, options = {}) {
  if (typeof scheduleDraw !== "function" || typeof tracker?.reset !== "function") {
    throw new TypeError("canvas benchmark");
  }
  const duration = Math.max(
    500,
    Math.min(10000, Math.trunc(Number(options.durationMs)) || 3000),
  );
  const requestFrame = options.requestFrame
    || ((callback) => requestAnimationFrame(callback));
  const now = options.now || (() => performance.now());
  tracker.reset();
  const startedAt = now();
  return new Promise((resolve) => {
    const sample = (timestamp) => {
      scheduleDraw();
      if (timestamp - startedAt >= duration) {
        requestFrame(() => resolve(tracker.report()));
        return;
      }
      requestFrame(sample);
    };
    requestFrame(sample);
  });
}

export function resolveEntitySprite(manifest, entity, motion, elapsedMs, reducedMotion) {
  const base = String(entity?.render_key || "");
  const direction = String(entity?.direction || "south");
  const state = motion === "moving" ? "moving" : "idle";
  let frameCount = 0;
  while (
    frameCount < MAX_ENTITY_FRAMES
    && manifest.sprites[`${base}.${direction}.${state}.frame_${frameCount}`]
  ) {
    frameCount += 1;
  }
  const frame = animationFrameIndex(elapsedMs, frameCount, reducedMotion);
  const candidates = entitySpriteCandidates(entity, state, frame);
  for (const candidate of candidates.slice(0, -1)) {
    if (manifest.sprites[candidate]) return manifest.sprites[candidate];
  }
  const sprite = resolveSprite(manifest, base);
  if (!sprite?.auto_mirror) return sprite;
  const westward = direction === "west"
    || direction === "northwest"
    || direction === "southwest";
  return {...sprite, flip_x: westward};
}

export function resolveSpriteLayers(cell) {
  const terrain = String(cell.terrain_base_key || cell.terrain_key || "unknown");
  const climate = String(cell.climate_variant || "base");
  const terrainKey = climate === "base"
    ? "terrain." + terrain
    : "terrain." + terrain + "." + climate;
  const layers = [terrainKey];
  if (cell.hydrology_key) {
    const hydrology = "hydrology." + cell.hydrology_key;
    layers.push(cell.hydrology_variant
      ? hydrology + "." + cell.hydrology_variant
      : hydrology);
  }
  if (cell.infrastructure_key) {
    const infrastructure = "infrastructure." + cell.infrastructure_key;
    layers.push(cell.infrastructure_variant
      ? infrastructure + "." + cell.infrastructure_variant
      : infrastructure);
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

export function spriteDestination(sprite, left, top, size) {
  const scale = Math.max(0.1, Math.min(1, Number(sprite?.scale) || 1));
  const anchorX = Math.max(
    0, Math.min(1, Number(sprite?.anchor_x ?? 0.5)),
  );
  const anchorY = Math.max(
    0, Math.min(1, Number(sprite?.anchor_y ?? 0.5)),
  );
  const width = size * scale;
  const height = size * scale;
  return {
    left: left + (size - width) * anchorX,
    top: top + (size - height) * anchorY,
    width,
    height,
  };
}

export function spriteRotation(sprite) {
  return Number(sprite?.rotation || 0) * Math.PI / 180;
}

export function puzzleEdgeProfile(x, y, axis, depth = 0.04, teeth = 4) {
  const count = Math.max(2, Math.min(16, Math.trunc(Number(teeth)) || 6));
  const maximum = Math.max(0.01, Math.min(0.5, Number(depth) || 0.04));
  const axisOffset = axis === "vertical" ? 1 : 0;
  const polarity = ((Math.trunc(Number(x)) + Math.trunc(Number(y)) + axisOffset) & 1)
    ? -1
    : 1;
  const profile = [0];
  for (let index = 0; index < count; index += 1) {
    const direction = index % 2 ? -polarity : polarity;
    for (const ratio of [0.25, 0.75, 1, 0.75, 0.25, 0]) {
      profile.push(Number((maximum * direction * ratio).toFixed(6)));
    }
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
    archiveControls: document.getElementById("archive-controls"),
    archivePrevious: document.getElementById("archive-previous"),
    archiveTimeline: document.getElementById("archive-timeline"),
    archiveNext: document.getElementById("archive-next"),
    archiveEvents: document.getElementById("archive-events"),
    archivePosition: document.getElementById("archive-position"),
    archiveStatus: document.getElementById("archive-status"),
  };
  const camera = {offsetX: 12, offsetY: 12, zoom: 1, tileSize: TILE_SIZE};
  const motionPreference = window.matchMedia("(prefers-reduced-motion: reduce)");
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
    renderMode: null,
    tileset: null,
    tilesets: [],
    mode: "live",
    archive: null,
    archiveRequest: 0,
    changedCells: new Set(),
    movingEntities: new Map(),
    reducedMotion: motionPreference.matches,
    performance: createCanvasPerformanceTracker(),
  };
  window.__chartographistPerformance = state.performance;

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
  state.performance.benchmark = (durationMs = 3000) => runCanvasBenchmark(
    scheduleDraw,
    state.performance,
    {durationMs},
  );

  function draw(timestamp = 0) {
    const drawStartedAt = performance.now();
    state.drawPending = false;
    for (const [identifier, startedAt] of state.movingEntities) {
      if (timestamp - startedAt >= ENTITY_MOTION_MS) {
        state.movingEntities.delete(identifier);
      }
    }
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
    const eachVisibleCell = (callback) => {
      for (let y = minY; y < maxY; y += 1) {
        for (let x = minX; x < maxX; x += 1) {
          const cell = state.cells.get(`${x},${y}`);
          if (!cell) continue;
          callback(cell, x, y, camera.offsetX + x * size, camera.offsetY + y * size);
        }
      }
    };
    eachVisibleCell((cell, x, y, left, top) => {
        context.fillStyle = terrainColor(cell);
        context.fillRect(left, top, Math.ceil(size), Math.ceil(size));
        if (state.tileset) {
          const manifest = state.tileset.manifest;
          const layers = resolveSpriteLayers(cell);
          const terrainSprite = resolveSprite(manifest, layers[0]);
          if (terrainSprite) drawSprite(terrainSprite, left, top, size);
        }
    });
    if (state.tileset?.manifest.edge_blending?.mode === "puzzle") {
      eachVisibleCell((cell, x, y, left, top) => {
        drawTerrainPuzzleEdge(
          cell,
          state.cells.get(`${x},${y - 1}`),
          "top",
          left,
          top,
          size,
        );
        drawTerrainPuzzleEdge(
          cell,
          state.cells.get(`${x - 1},${y}`),
          "left",
          left,
          top,
          size,
        );
      });
    }
    eachVisibleCell((cell, x, y, left, top) => {
        if (state.tileset) {
          const manifest = state.tileset.manifest;
          const layers = resolveSpriteLayers(cell);
          for (const visualKey of layers.slice(1)) {
            const entityId = Number(cell.entity?.entity_id);
            const startedAt = state.movingEntities.get(entityId);
            const isMoving = (
              visualKey.startsWith("entity.")
              && startedAt !== undefined
              && timestamp - startedAt < ENTITY_MOTION_MS
            );
            const elapsed = isMoving ? Math.max(0, timestamp - startedAt) : 0;
            const sprite = visualKey.startsWith("entity.") && cell.entity
              ? resolveEntitySprite(
                manifest,
                cell.entity,
                isMoving ? "moving" : "idle",
                elapsed,
                state.reducedMotion,
              )
              : resolveSprite(manifest, visualKey);
            if (!sprite) continue;
            const bob = isMoving && !state.reducedMotion
              ? Math.abs(Math.sin(elapsed / ENTITY_FRAME_MS * Math.PI)) * size * 0.04
              : 0;
            drawSprite(sprite, left, top - bob, size);
          }
        }
        if (state.changedCells.has(`${x},${y}`)) {
          context.strokeStyle = "#66d9ef";
          context.lineWidth = 2;
          context.strokeRect(left + 2, top + 2, Math.max(1, size - 4), Math.max(1, size - 4));
        }
        if (state.selected?.x === x && state.selected?.y === y) {
          context.strokeStyle = "#f5cf62";
          context.lineWidth = 2;
          context.strokeRect(left + 1, top + 1, Math.max(1, size - 2), Math.max(1, size - 2));
        }
    });
    state.performance.record(
      timestamp,
      performance.now() - drawStartedAt,
      Math.max(0, maxX - minX) * Math.max(0, maxY - minY),
    );
    if (state.movingEntities.size && !state.reducedMotion) scheduleDraw();
  }

  function drawSprite(sprite, left, top, size) {
    const manifest = state.tileset.manifest;
    const sheetId = sprite.sheet || manifest.default_sheet || "default";
    const sheet = manifest.sheets?.[sheetId] || manifest;
    const image = state.tileset.images?.[sheetId] || state.tileset.image;
    const destination = spriteDestination(sprite, left, top, size);
    const rotation = spriteRotation(sprite);
    if (rotation || sprite.flip_x) {
      context.save();
      context.translate(
        destination.left + destination.width / 2,
        destination.top + destination.height / 2,
      );
      context.rotate(rotation);
      context.scale(sprite.flip_x ? -1 : 1, 1);
      context.drawImage(
        image,
        sprite.x * sheet.tile_width,
        sprite.y * sheet.tile_height,
        sheet.tile_width,
        sheet.tile_height,
        -destination.width / 2,
        -destination.height / 2,
        Math.ceil(destination.width),
        Math.ceil(destination.height),
      );
      context.restore();
      return;
    }
    context.drawImage(
      image,
      sprite.x * sheet.tile_width,
      sprite.y * sheet.tile_height,
      sheet.tile_width,
      sheet.tile_height,
      destination.left,
      destination.top,
      Math.ceil(destination.width),
      Math.ceil(destination.height),
    );
  }

  function drawTerrainPuzzleEdge(cell, neighbor, direction, left, top, size) {
    if (!neighbor || resolveSpriteLayers(neighbor)[0] === resolveSpriteLayers(cell)[0]) return;
    const manifest = state.tileset.manifest;
    const neighborSprite = resolveSprite(manifest, resolveSpriteLayers(neighbor)[0]);
    const cellSprite = resolveSprite(manifest, resolveSpriteLayers(cell)[0]);
    if (!neighborSprite || !cellSprite) return;
    const blending = manifest.edge_blending;
    const profile = puzzleEdgeProfile(
      cell.x,
      cell.y,
      direction === "top" ? "horizontal" : "vertical",
      blending.depth,
      blending.teeth,
    );
    context.save();
    context.beginPath();
    if (direction === "top") {
      context.moveTo(left, top);
      context.lineTo(left + size, top);
      for (let index = profile.length - 1; index >= 0; index -= 1) {
        const depth = Math.max(0, profile[index]);
        context.lineTo(
          left + (index / (profile.length - 1)) * size,
          top + depth * size,
        );
      }
    } else {
      context.moveTo(left, top);
      context.lineTo(left, top + size);
      for (let index = profile.length - 1; index >= 0; index -= 1) {
        const depth = Math.max(0, profile[index]);
        context.lineTo(
          left + depth * size,
          top + (index / (profile.length - 1)) * size,
        );
      }
    }
    context.closePath();
    context.clip();
    drawSprite(neighborSprite, left, top, size);
    context.restore();

    context.save();
    context.beginPath();
    if (direction === "top") {
      context.moveTo(left, top);
      context.lineTo(left + size, top);
      for (let index = profile.length - 1; index >= 0; index -= 1) {
        const depth = Math.max(0, -profile[index]);
        context.lineTo(
          left + (index / (profile.length - 1)) * size,
          top - depth * size,
        );
      }
    } else {
      context.moveTo(left, top);
      context.lineTo(left, top + size);
      for (let index = profile.length - 1; index >= 0; index -= 1) {
        const depth = Math.max(0, -profile[index]);
        context.lineTo(
          left - depth * size,
          top + (index / (profile.length - 1)) * size,
        );
      }
    }
    context.closePath();
    context.clip();
    drawSprite(
      cellSprite,
      direction === "left" ? left - size : left,
      direction === "top" ? top - size : top,
      size,
    );
    context.restore();
  }

  function rebuildCellIndex() {
    state.cells = new Map(
      (state.snapshot?.cells || []).map((cell) => [`${cell.x},${cell.y}`, cell]),
    );
  }

  function markEntityMovements(previousCells, currentCells) {
    if (state.reducedMotion) {
      state.movingEntities.clear();
      return;
    }
    const now = performance.now();
    for (const identifier of movingEntityIds(previousCells, currentCells)) {
      state.movingEntities.set(identifier, now);
    }
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

  function displayKey(key) {
    return String(key)
      .replaceAll("_", " ")
      .replace(/\b\w/g, (character) => character.toUpperCase());
  }

  function displayValue(value) {
    if (typeof value === "boolean") return value ? "✓" : "—";
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "number") {
      return new Intl.NumberFormat(state.meta?.language || undefined, {
        maximumFractionDigits: 2,
      }).format(value);
    }
    return String(value);
  }

  function appendStructuredValue(container, value) {
    if (Array.isArray(value)) {
      if (!value.length) {
        const empty = document.createElement("p");
        empty.className = "panel-empty";
        empty.textContent = label("empty");
        container.append(empty);
        return;
      }
      const grid = document.createElement("div");
      grid.className = "panel-grid";
      for (const entry of value) {
        const card = document.createElement("article");
        card.className = "panel-card";
        appendStructuredValue(card, entry);
        grid.append(card);
      }
      container.append(grid);
      return;
    }
    if (value && typeof value === "object") {
      const fields = document.createElement("dl");
      fields.className = "panel-fields";
      for (const [key, child] of Object.entries(value)) {
        if (child && typeof child === "object") {
          const section = document.createElement("section");
          section.className = "panel-section";
          const heading = document.createElement("h3");
          heading.textContent = displayKey(key);
          section.append(heading);
          appendStructuredValue(section, child);
          container.append(section);
          continue;
        }
        const term = document.createElement("dt");
        term.textContent = displayKey(key);
        const detail = document.createElement("dd");
        detail.textContent = displayValue(child);
        fields.append(term, detail);
      }
      if (fields.childElementCount) container.append(fields);
      return;
    }
    const text = document.createElement("p");
    text.textContent = displayValue(value);
    container.append(text);
  }

  function renderStructuredPanel(value) {
    elements.panel.replaceChildren();
    if (
      value === null
      || value === undefined
      || (Array.isArray(value) && value.length === 0)
      || (typeof value === "object" && !Array.isArray(value) && Object.keys(value).length === 0)
    ) {
      const empty = document.createElement("p");
      empty.className = "panel-empty";
      empty.textContent = label("empty");
      elements.panel.append(empty);
      return;
    }
    appendStructuredValue(elements.panel, value);
  }

  function renderBestiary(bestiary) {
    elements.panel.replaceChildren();
    const groups = [
      ["fauna", "bestiary_fauna"],
      ["species", "bestiary_species"],
      ["religions", "bestiary_religions"],
      ["settlements", "bestiary_settlements"],
    ];
    for (const [key, headingKey] of groups) {
      const section = document.createElement("section");
      section.className = "bestiary-group";
      const heading = document.createElement("h3");
      heading.textContent = label(headingKey);
      section.append(heading);
      const entries = bestiary?.[key] || [];
      if (!entries.length) {
        const empty = document.createElement("p");
        empty.className = "panel-empty";
        empty.textContent = label("empty");
        section.append(empty);
      } else {
        const grid = document.createElement("div");
        grid.className = "bestiary-grid";
        for (const entry of entries) {
          const card = document.createElement("article");
          card.className = "bestiary-card";
          const title = document.createElement("h4");
          const emblem = entry.symbols || entry.symbol || "";
          title.textContent = [emblem, entry.name].filter(Boolean).join(" ");
          card.append(title);
          const details = Object.fromEntries(
            Object.entries(entry).filter(([field]) => !["name", "symbol", "symbols"].includes(field)),
          );
          appendStructuredValue(card, details);
          grid.append(card);
        }
        section.append(grid);
      }
      elements.panel.append(section);
    }
  }

  function renderPanel() {
    const panels = state.snapshot?.panels || {};
    if (state.activePanel === "bestiary") {
      renderBestiary(panelForView(panels, state.activePanel));
    } else {
      renderStructuredPanel(panelForView(panels, state.activePanel));
    }
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
    const previousCells = rebuildCells ? [...state.cells.values()] : null;
    state.snapshot = snapshot;
    if (rebuildCells) {
      rebuildCellIndex();
      markEntityMovements(previousCells, [...state.cells.values()]);
    }
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

  function updateArchivePosition() {
    if (!state.archive || !state.snapshot) return;
    const revision = Number(state.snapshot.revision);
    elements.archiveTimeline.value = String(revision);
    elements.archivePosition.textContent =
      `${label("archive_revision")} ${revision} · ${label("cycle")} ${state.snapshot.cycle}`;
    elements.archivePrevious.disabled = revision <= state.archive.first_revision;
    elements.archiveNext.disabled = revision >= state.archive.last_revision;
  }

  async function loadArchiveSnapshot(query, center = false) {
    const requestId = state.archiveRequest + 1;
    state.archiveRequest = requestId;
    elements.archiveStatus.dataset.state = "loading";
    elements.archiveStatus.textContent = label("archive_loading");
    const previousRevision = Number(state.snapshot?.revision);
    const parameters = new URLSearchParams(query);
    try {
      const response = await fetch(
        `/api/v1/snapshot?${parameters}`,
        {cache: "no-store"},
      );
      if (!response.ok) throw new Error(`archive snapshot ${response.status}`);
      const snapshot = await response.json();
      if (requestId !== state.archiveRequest) return;
      state.changedCells = new Set();
      if (
        Number.isFinite(previousRevision)
        && previousRevision !== Number(snapshot.revision)
      ) {
        const fromRevision = Math.min(previousRevision, Number(snapshot.revision));
        const toRevision = Math.max(previousRevision, Number(snapshot.revision));
        const comparisonResponse = await fetch(`/api/v1/compare?from_revision=${fromRevision}&to_revision=${toRevision}`, {
          cache: "no-store",
        });
        if (!comparisonResponse.ok) {
          throw new Error(`archive compare ${comparisonResponse.status}`);
        }
        const comparison = await comparisonResponse.json();
        if (requestId !== state.archiveRequest) return;
        state.changedCells = new Set(
          (comparison.changed_cells || []).map((cell) => `${cell.x},${cell.y}`),
        );
      }
      consumeSnapshot(snapshot, center);
      updateArchivePosition();
      elements.archiveStatus.dataset.state = "ready";
      elements.archiveStatus.textContent =
        `${label("archive_ready")} · ${label("archive_changed_cells")}: ${state.changedCells.size}`;
    } catch {
      if (requestId !== state.archiveRequest) return;
      elements.archiveStatus.dataset.state = "error";
      elements.archiveStatus.textContent = label("archive_error");
    }
  }

  async function initializeArchive(meta) {
    state.mode = "archive";
    state.archive = meta.archive;
    elements.archiveControls.hidden = false;
    for (const identifier of ["pause", "resume", "step", "speed"]) {
      document.getElementById(identifier).disabled = true;
    }
    elements.archiveTimeline.min = String(meta.archive.first_revision);
    elements.archiveTimeline.max = String(meta.archive.last_revision);
    elements.archiveTimeline.value = String(meta.archive.last_revision);
    const response = await fetch("/api/v1/timeline", {cache: "no-store"});
    if (!response.ok) throw new Error(`archive timeline ${response.status}`);
    const timeline = await response.json();
    elements.archiveEvents.replaceChildren();
    for (const event of timeline.events || []) {
      const option = document.createElement("option");
      option.value = String(event.cycle);
      option.textContent = `${event.cycle} · ${event.title || event.name || event.chronicle_id}`;
      elements.archiveEvents.append(option);
    }
    elements.archiveEvents.disabled = elements.archiveEvents.options.length === 0;
    await loadArchiveSnapshot({revision: meta.archive.last_revision}, true);
  }

  async function refreshSnapshot(center = false) {
    const response = await fetch("/api/v1/snapshot", {cache: "no-store"});
    if (!response.ok) throw new Error(`snapshot ${response.status}`);
    consumeSnapshot(await response.json(), center);
  }

  function sendCommand(command, value) {
    if (state.mode === "archive") return;
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
    const urls = manifest.sheet_urls || {
      [manifest.default_sheet || "default"]: manifest.image_url,
    };
    const images = {};
    await Promise.all(Object.entries(urls).map(async ([sheetId, url]) => {
      const image = new Image();
      image.decoding = "async";
      image.src = url;
      await image.decode();
      images[sheetId] = image;
    }));
    const defaultSheet = manifest.default_sheet || Object.keys(images)[0];
    const image = images[defaultSheet];
    state.tileset = {manifest, image, images};
    state.renderMode = manifest.id;
    scheduleDraw();
  }

  function configureRenderModes(meta) {
    state.tilesets = meta.tilesets || [];
    elements.renderMode.replaceChildren();
    for (const summary of state.tilesets) {
      const option = document.createElement("option");
      option.value = summary.id;
      option.textContent = label("sprite_theme") + " · " + summary.name;
      elements.renderMode.append(option);
    }
    const initialTileset = state.tilesets[0] || null;
    elements.renderMode.value = initialTileset?.id || "";
    return initialTileset;
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
        const previousCells = [...state.cells.values()];
        const next = applyDeltaToSnapshot(
          state.snapshot,
          message.payload,
          state.cells,
        );
        if (next) {
          markEntityMovements(previousCells, [...state.cells.values()]);
          consumeSnapshot(next, false, false);
        }
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
    } else if (state.mode === "archive" && (event.key === "[" || event.key === "]")) {
      event.preventDefault();
      const revision = archiveRevisionStep(
        state.snapshot?.revision,
        state.archive.first_revision,
        state.archive.last_revision,
        event.key === "[" ? -1 : 1,
      );
      loadArchiveSnapshot({revision});
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
  elements.archivePrevious.addEventListener("click", () => {
    const revision = archiveRevisionStep(
      state.snapshot.revision, state.archive.first_revision, state.archive.last_revision, -1,
    );
    loadArchiveSnapshot({revision});
  });
  elements.archiveNext.addEventListener("click", () => {
    const revision = archiveRevisionStep(
      state.snapshot.revision, state.archive.first_revision, state.archive.last_revision, 1,
    );
    loadArchiveSnapshot({revision});
  });
  elements.archiveTimeline.addEventListener("change", () => {
    loadArchiveSnapshot({revision: elements.archiveTimeline.value});
  });
  elements.archiveEvents.addEventListener("change", () => {
    loadArchiveSnapshot({cycle: elements.archiveEvents.value});
  });
  elements.renderMode.addEventListener("change", async () => {
    const identifier = elements.renderMode.value;
    const summary = state.tilesets.find((item) => item.id === identifier);
    if (!summary) {
      elements.renderMode.value = state.renderMode || "";
      return;
    }
    try {
      await loadTileset(summary);
    } catch {
      elements.renderMode.value = state.renderMode || "";
      scheduleDraw();
    }
  });
  document.querySelectorAll("[data-panel]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activePanel = button.dataset.panel;
      renderPanel();
    });
  });
  motionPreference.addEventListener?.("change", (event) => {
    state.reducedMotion = event.matches;
    if (event.matches) state.movingEntities.clear();
    scheduleDraw();
  });

  new ResizeObserver(resizeCanvas).observe(canvas);
  fetch("/api/v1/meta", {cache: "no-store"})
    .then((response) => response.ok ? response.json() : Promise.reject(new Error("meta")))
    .then(async (meta) => {
      state.mode = meta.mode === "archive" ? "archive" : "live";
      state.labels = meta.labels || {};
      document.documentElement.lang = meta.language || "fr";
      elements.speed.value = String(meta.runtime?.tick_interval ?? 0.15);
      localize();
      const initialTileset = configureRenderModes(meta);
      if (initialTileset) {
        try {
          await loadTileset(initialTileset);
        } catch {
          state.renderMode = null;
          state.tileset = null;
          elements.renderMode.value = "";
        }
      }
      if (meta.mode === "archive") {
        await initializeArchive(meta);
      } else {
        connect();
      }
    })
    .catch(() => setConnection("disconnected"));
  resizeCanvas();
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", startClient);
}
