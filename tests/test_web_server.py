import base64
import ast
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from core.translator import Translator
from core.system import load_launch_options
from core.web_server import (
    _publish_cycles,
    create_archive_web_app,
    run_archive_web_server,
    create_web_app,
    validate_web_bind,
)


ROOT = Path(__file__).resolve().parents[1]


class FakeWebHost:
    def __init__(self):
        self.engine = SimpleNamespace(
            world={"cycle": 4},
            stats={"seed": 12},
            config={"world_name": "Web Test"},
            inspect_entity=lambda entity_id: (
                {"entity_id": entity_id, "name": "Ada"}
                if entity_id == 7 else None
            ),
        )
        self.revision = 3
        self.paused = False
        self.tick_interval = 0.15
        self.commands = []

    def snapshot(self):
        return {
            "schema_version": 1,
            "revision": self.revision,
            "cycle": self.engine.world["cycle"],
            "cells": [],
            "panels": {},
        }

    def submit_command(self, kind, value=None):
        if kind not in {"pause", "resume", "step", "speed", "save", "stop"}:
            return False
        if kind == "speed" and not isinstance(value, (int, float)):
            return False
        if kind != "speed" and value is not None:
            return False
        self.commands.append((kind, value))
        return True


class WebServerContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Translator.load("fr")
        self.host = FakeWebHost()
        self.client = TestClient(TestServer(create_web_app(self.host)))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_meta_snapshot_and_static_entrypoint_are_versioned(self):
        response = await self.client.get("/api/v1/meta")
        self.assertEqual(response.status, 200)
        meta = await response.json()
        self.assertEqual(meta["api_version"], 1)
        self.assertEqual(meta["mode"], "live")
        self.assertEqual(meta["presentation_schema_version"], 1)
        self.assertEqual(meta["world"]["name"], "Web Test")
        self.assertEqual(meta["language"], "fr")
        self.assertEqual(meta["labels"]["pause"], "Pause")
        self.assertEqual(
            meta["labels"]["simulation_controls"], "Contrôles de simulation"
        )
        self.assertEqual(meta["labels"]["render_mode"], "Rendu")
        self.assertEqual(meta["labels"]["bestiary"], "Bestiaire")
        self.assertEqual(
            [item["id"] for item in meta["tilesets"]],
            ["interwoven"],
        )
        self.assertEqual(
            meta["tilesets"][0]["manifest_url"],
            "/api/v1/tilesets/interwoven",
        )
        interwoven = meta["tilesets"][0]
        self.assertEqual(interwoven["name"], "Chartographist Entrelacé")
        self.assertIn("websocket", meta["capabilities"])
        self.assertIn("spritesheets", meta["capabilities"])

        response = await self.client.get("/api/v1/snapshot")
        self.assertEqual(await response.json(), self.host.snapshot())

        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertTrue(response.content_type.startswith("text/html"))
        self.assertIn("Chartographist", await response.text())

    async def test_web_meta_does_not_expose_the_removed_glyph_mode(self):
        response = await self.client.get("/api/v1/meta")
        self.assertEqual(response.status, 200)
        self.assertNotIn("glyph_theme", (await response.json())["labels"])


    async def test_inspection_is_defensive_and_unknown_entity_is_404(self):
        response = await self.client.get("/api/v1/entities/7")
        self.assertEqual((await response.json())["entity_id"], 7)
        response = await self.client.get("/api/v1/entities/99")
        self.assertEqual(response.status, 404)
        response = await self.client.get("/api/v1/entities/not-an-id")
        self.assertEqual(response.status, 404)

    async def test_commands_are_whitelisted_and_do_not_accept_paths(self):
        response = await self.client.post(
            "/api/v1/commands", json={"command": "pause"}
        )
        self.assertEqual(response.status, 202)
        self.assertEqual(self.host.commands[-1], ("pause", None))

        response = await self.client.post(
            "/api/v1/commands",
            json={"command": "save", "value": "/tmp/untrusted.chart"},
        )
        self.assertEqual(response.status, 400)
        response = await self.client.post(
            "/api/v1/commands", json={"command": "shell"}
        )
        self.assertEqual(response.status, 400)

    async def test_foreign_origins_are_rejected(self):
        response = await self.client.get(
            "/api/v1/snapshot", headers={"Origin": "https://hostile.example"}
        )
        self.assertEqual(response.status, 403)

    async def test_websocket_publishes_snapshot_and_accepts_commands(self):
        socket = await self.client.ws_connect("/api/v1/stream")
        initial = await socket.receive_json()
        self.assertEqual(initial["type"], "snapshot")
        self.assertEqual(initial["payload"]["revision"], 3)
        await socket.send_json({"command": "speed", "value": 0.25})
        accepted = await socket.receive_json()
        self.assertEqual(accepted, {"type": "command", "accepted": True})
        self.assertEqual(self.host.commands[-1], ("speed", 0.25))
        await socket.close()

    async def test_oversized_command_payload_is_rejected(self):
        response = await self.client.post(
            "/api/v1/commands",
            data=b"x" * (65 * 1024),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status, 413)

    async def test_cycle_publisher_emits_a_versioned_delta(self):
        class AdvancingHost(FakeWebHost):
            stopped = False
            tick_interval = 0

            def tick(self):
                self.revision += 1
                self.engine.world["cycle"] += 1
                self.stopped = True
                return self.snapshot()

        class Socket:
            def __init__(self):
                self.messages = []

            async def send_json(self, message):
                self.messages.append(message)

        host = AdvancingHost()
        socket = Socket()
        await _publish_cycles(host, {socket})
        self.assertEqual(socket.messages[0]["type"], "delta")
        self.assertEqual(socket.messages[0]["payload"]["from_revision"], 3)
        self.assertEqual(socket.messages[0]["payload"]["to_revision"], 4)

    async def test_cycle_publisher_skips_projection_without_clients(self):
        class DeferredHost(FakeWebHost):
            stopped = False
            tick_interval = 0

            def __init__(self):
                super().__init__()
                self.snapshot_calls = 0
                self.publish_flags = []

            def snapshot(self):
                self.snapshot_calls += 1
                return super().snapshot()

            def tick(self, *, publish_snapshot=True):
                self.publish_flags.append(publish_snapshot)
                self.engine.world["cycle"] += 1
                self.stopped = True
                return None

        host = DeferredHost()
        await _publish_cycles(host, set())
        self.assertEqual(host.snapshot_calls, 0)
        self.assertEqual(host.publish_flags, [False])

    async def test_cycle_publisher_resumes_with_delta_after_client_returns(self):
        sockets = set()

        class Socket:
            def __init__(self):
                self.messages = []

            async def send_json(self, message):
                self.messages.append(message)

        socket = Socket()

        class ReconnectingHost(FakeWebHost):
            stopped = False
            tick_interval = 0

            def snapshot(self):
                return {
                    "schema_version": 1,
                    "revision": self.revision,
                    "cycle": self.engine.world["cycle"],
                    "clock": {},
                    "cells": [],
                    "logs": [],
                    "panels": {},
                }

            def tick(self, *, publish_snapshot=True):
                self.revision += 1
                self.engine.world["cycle"] += 1
                if not publish_snapshot:
                    sockets.add(socket)
                    return None
                self.stopped = True
                return self.snapshot()

        host = ReconnectingHost()
        await _publish_cycles(host, sockets)
        self.assertEqual(len(socket.messages), 1)
        self.assertEqual(socket.messages[0]["type"], "delta")
        self.assertEqual(
            (
                socket.messages[0]["payload"]["from_revision"],
                socket.messages[0]["payload"]["to_revision"],
            ),
            (4, 5),
        )

    async def test_static_client_assets_are_whitelisted(self):
        for path, content_type in (
            ("/assets/app.js", "application/javascript"),
            ("/assets/styles.css", "text/css"),
        ):
            response = await self.client.get(path)
            self.assertEqual(response.status, 200)
            self.assertTrue(response.content_type.startswith(content_type))
        response = await self.client.get("/assets/unknown.js")
        self.assertEqual(response.status, 404)
        response = await self.client.get("/api/v1/tilesets/interwoven")
        self.assertEqual(response.status, 200)
        interwoven = await response.json()
        self.assertEqual(interwoven["id"], "interwoven")
        self.assertEqual(interwoven["tile_width"], interwoven["tile_height"])
        self.assertEqual(interwoven["edge_blending"]["mode"], "puzzle")
        self.assertEqual(
            interwoven["sheet_urls"]["entities"],
            "/assets/tilesets/interwoven/entities.png",
        )
        response = await self.client.get(
            "/assets/tilesets/interwoven/atlas.png"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        response = await self.client.get(
            "/assets/tilesets/interwoven/entities.png"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        response = await self.client.get("/api/v1/tilesets/unknown")
        self.assertEqual(response.status, 404)
        response = await self.client.get(
            "/assets/tilesets/interwoven/unknown.png"
        )
        self.assertEqual(response.status, 404)

    async def test_interwoven_water_terrain_sheets_are_served(self):
        response = await self.client.get("/api/v1/tilesets/interwoven")
        self.assertEqual(response.status, 200)
        manifest = await response.json()
        for identifier, filename in (
            ("ocean", "ocean.png"),
            ("beach", "beach.png"),
            ("climate", "climate.png"),
            ("rivers", "rivers.png"),
            ("roads", "roads.png"),
            ("cultures", "cultures.png"),
            ("water_climate", "water-climate.png"),
        ):
            with self.subTest(identifier=identifier):
                self.assertEqual(
                    manifest["sheet_urls"][identifier],
                    f"/assets/tilesets/interwoven/{filename}",
                )
                response = await self.client.get(
                    f"/assets/tilesets/interwoven/{filename}"
                )
                self.assertEqual(response.status, 200)
                self.assertEqual(response.content_type, "image/png")


    def test_browser_client_has_canvas_controls_panels_and_accessibility(self):
        markup = (ROOT / "web/index.html").read_text(encoding="utf-8")
        script = (ROOT / "web/app.js").read_text(encoding="utf-8")
        styles = (ROOT / "web/styles.css").read_text(encoding="utf-8")
        for fragment in (
            'id="world-map"',
            'id="pause"',
            'id="step"',
            'id="speed"',
            'id="render-mode"',
            'id="logs"',
            'id="panel-content"',
            'data-panel="bestiary"',
            'id="selection"',
            'tabindex="0"',
            'aria-live="polite"',
            'data-i18n-aria="simulation_controls"',
            'data-i18n-aria="observatory"',
            'id="archive-controls"',
            'id="archive-previous"',
            'id="archive-timeline"',
            'id="archive-next"',
            'id="archive-events"',
            'id="archive-status"',
            'data-i18n-aria="archive_navigation"',
        ):
            self.assertIn(fragment, markup)
        self.assertNotIn('aria-label="Simulation"', markup)
        self.assertNotIn('aria-label="Observatory"', markup)
        self.assertNotIn('value="glyphs"', markup)
        self.assertNotIn('data-i18n="glyph_theme"', markup)
        self.assertNotIn('"glyphs"', script)
        self.assertNotIn("elements.panel.textContent = JSON.stringify", script)
        self.assertNotIn('<pre id="panel-content"', markup)
        self.assertIn("await loadTileset(initialTileset)", script)

        for fragment in (
            "new WebSocket",
            "applyDeltaToSnapshot",
            "requestAnimationFrame",
            "addEventListener(\"wheel\"",
            "addEventListener(\"pointerdown\"",
            "addEventListener(\"keydown\"",
            "loadTileset",
            "resolveSpriteLayers",
            "renderBestiary",
            "puzzleEdgeProfile",
            "drawImage",
            "initializeArchive",
            'meta.mode === "archive"',
            'fetch("/api/v1/timeline"',
            'fetch(`/api/v1/compare?',
            "archiveRevisionStep",
            "changedCells",
            'matchMedia("(prefers-reduced-motion: reduce)")',
            "resolveEntitySprite",
            "movingEntityIds",
        ):
            self.assertIn(fragment, script)
        self.assertIn("@media", styles)
        self.assertIn("prefers-reduced-motion", styles)

    def test_browser_client_delta_and_geometry_helpers_execute_in_node(self):
        executable = shutil.which("node")
        if executable is None:
            self.skipTest("Node.js unavailable")
        source = (ROOT / "web/app.js").read_bytes()
        encoded = base64.b64encode(source).decode("ascii")
        program = f"""
const client = await import("data:text/javascript;base64,{encoded}");
const snapshot = {{
  revision: 1,
  cells: [
    {{x: 0, y: 0, visible_key: "terrain.grassland"}},
    {{x: 1, y: 0, visible_key: "terrain.sand"}}
  ],
  logs: [],
  panels: {{}}
}};
const delta = {{
  from_revision: 1,
  to_revision: 2,
  cycle: 8,
  cells: [{{x: 1, y: 0, visible_key: "hydrology.river"}}],
  logs: ["ok"],
  panels: {{systems: []}}
}};
const next = client.applyDeltaToSnapshot(snapshot, delta);
if (next.revision !== 2 || next.cells[1].visible_key !== "hydrology.river") {{
  throw new Error("delta contract");
}}
const indexedCells = new Map(snapshot.cells.map((item) => [item.x + "," + item.y, item]));
const optimized = client.applyDeltaToSnapshot(snapshot, delta, indexedCells);
if (optimized.cells !== snapshot.cells) {{
  throw new Error("optimized delta copied all cells");
}}
if (indexedCells.get("1,0").visible_key !== "hydrology.river") {{
  throw new Error("optimized delta index");
}}
if (client.boundedZoom(99) !== 4 || client.boundedZoom(0) !== 0.5) {{
  throw new Error("zoom bounds");
}}
if (
  client.archiveRevisionStep(2, 2, 5, -1) !== 2
  || client.archiveRevisionStep(3, 2, 5, 1) !== 4
  || client.archiveRevisionStep(5, 2, 5, 1) !== 5
) {{
  throw new Error("archive revision bounds");
}}
const cell = client.cellAtCanvasPoint(37, 19, {{
  offsetX: 1, offsetY: 1, zoom: 1, tileSize: 18
}});
if (cell.x !== 2 || cell.y !== 1) throw new Error("geometry contract");
const manifest = {{
  tile_width: 16,
  tile_height: 16,
  fallback: "fallback.unknown",
  sheets: {{
    terrain: {{tile_width: 16, tile_height: 16}},
    entities: {{tile_width: 32, tile_height: 32}}
  }},
  sprites: {{
    "terrain.grassland": {{x: 1, y: 0, sheet: "terrain", scale: 1, anchor_x: 0.5, anchor_y: 0.5}},
    "site.ruins": {{x: 2, y: 0}},
    "entity.animal.wolf": {{x: 3, y: 0, sheet: "entities", scale: 0.7, anchor_x: 0.5, anchor_y: 1}},
    "fallback.unknown": {{x: 0, y: 0}}
  }}
}};
const layers = client.resolveSpriteLayers({{
  terrain_key: "grassland",
  terrain_base_key: "temperate_forest",
  climate_variant: "winter",
  hydrology_key: "river",
  hydrology_variant: "corner_ne",
  infrastructure_key: "road",
  infrastructure_variant: "corner_sw",
  site_key: "ruins.ancient",
  entity: {{render_key: "entity.animal.wolf"}}
}});
if (layers.join("|") !== "terrain.temperate_forest.winter|hydrology.river.corner_ne|infrastructure.road.corner_sw|site.ruins.ancient|entity.animal.wolf") {{
  throw new Error("layer contract");
}}
const siteSprite = client.resolveSprite(manifest, "site.ruins.ancient");
const fallbackSprite = client.resolveSprite(manifest, "mod.unknown");
if (siteSprite.x !== 2 || fallbackSprite.x !== 0) {{
  throw new Error("sprite fallback contract");
}}
const destination = client.spriteDestination(
  manifest.sprites["entity.animal.wolf"], 10, 20, 100
);
if (
  destination.left !== 25 || destination.top !== 50
  || destination.width !== 70 || destination.height !== 70
) {{
  throw new Error("scaled transparent entity destination");
}}
const horizontal = client.puzzleEdgeProfile(4, 7, "horizontal", 0.04, 4);
const reversed = client.puzzleEdgeProfile(4, 8, "horizontal", 0.04, 4);
if (horizontal.length !== 25 || horizontal[0] !== 0 || horizontal.at(-1) !== 0) {{
  throw new Error("puzzle edge geometry contract");
}}
if (horizontal.some((value) => Math.abs(value) > 0.04)) {{
  throw new Error("puzzle micro-depth contract");
}}
if (horizontal.some((value, index) => Math.abs(value + reversed[index]) > 1e-9)) {{
  throw new Error("neighbor puzzle complement contract");
}}
const centered = client.spriteDestination(
  {{scale: 0.68, anchor_x: 0.5, anchor_y: 0.5}}, 10, 20, 100
);
if (centered.left !== 26 || centered.top !== 36 || centered.width !== 68 || centered.height !== 68) {{
  throw new Error("centered settlement destination");
}}
const panels = {{
  metrics: {{population: 12}},
  systems: [{{name: "climate", enabled: true, config: {{debug: true}}}}],
  bestiary: {{fauna: [{{name: "Wolf"}}], species: [], religions: [], settlements: []}}
}};
const overview = client.panelForView(panels, "overview");
if (overview !== panels.metrics || "systems" in overview || "config" in overview) {{
  throw new Error("overview exposes configuration state");
}}
if (client.panelForView(panels, "bestiary") !== panels.bestiary) {{
  throw new Error("bestiary panel selection contract");
}}
if (
  client.spriteRotation({{rotation: 90}}) !== Math.PI / 2
  || client.spriteRotation({{rotation: 270}}) !== Math.PI * 1.5
  || client.spriteRotation({{}}) !== 0
) {{
  throw new Error("sprite quarter-turn contract");
}}
const entity = {{entity_id: 7, render_key: "entity.human.trader", direction: "east"}};
const candidates = client.entitySpriteCandidates(entity, "moving", 1);
if (candidates.join("|") !== [
  "entity.human.trader.east.moving.frame_1",
  "entity.human.trader.east.moving.frame_0",
  "entity.human.trader.east",
  "entity.human.trader"
].join("|")) {{
  throw new Error("directional frame fallback contract");
}}
if (
  client.animationFrameIndex(260, 3, false) !== 2
  || client.animationFrameIndex(260, 3, true) !== 0
  || client.animationFrameIndex(999, 0, false) !== 0
) {{
  throw new Error("bounded reduced-motion frame contract");
}}
const previousCells = [
  {{x: 0, y: 0, entity: {{entity_id: 7}}}},
  {{x: 3, y: 1, entity: {{entity_id: 9}}}}
];
const currentCells = [
  {{x: 1, y: 0, entity: {{entity_id: 7}}}},
  {{x: 3, y: 1, entity: {{entity_id: 9}}}}
];
const moving = client.movingEntityIds(previousCells, currentCells);
if (moving.size !== 1 || !moving.has(7)) {{
  throw new Error("client-only movement detection contract");
}}
const performanceTracker = client.createCanvasPerformanceTracker(3);
performanceTracker.record(100, 5, 400);
performanceTracker.record(116, 7, 400);
performanceTracker.record(132, 9, 420);
performanceTracker.record(148, 11, 420);
const performanceReport = performanceTracker.report();
if (
  performanceReport.frames !== 3
  || performanceReport.fps !== 62.5
  || performanceReport.draw_ms.median !== 9
  || performanceReport.draw_ms.p95 !== 11
  || performanceReport.visible_cells !== 420
) {{
  throw new Error("bounded canvas performance contract");
}}
performanceTracker.reset();
if (performanceTracker.report().frames !== 0) {{
  throw new Error("canvas performance reset contract");
}}
const burstTracker = client.createCanvasPerformanceTracker(5);
burstTracker.record(0, 4, 300);
burstTracker.record(16, 4, 300);
burstTracker.record(1016, 4, 300);
burstTracker.record(1032, 4, 300);
if (burstTracker.report().fps !== 62.5) {{
  throw new Error("idle time polluted active canvas fps");
}}
let benchmarkClock = 0;
let scheduledDraws = 0;
const benchmarkTracker = client.createCanvasPerformanceTracker(120);
const benchmarkReport = await client.runCanvasBenchmark(
  () => {{
    scheduledDraws += 1;
    benchmarkTracker.record(benchmarkClock, 2, 300);
  }},
  benchmarkTracker,
  {{
    durationMs: 500,
    now: () => 0,
    requestFrame: (callback) => {{
      benchmarkClock += 16;
      callback(benchmarkClock);
    }},
  }},
);
if (
  scheduledDraws !== 32
  || benchmarkReport.frames !== 32
  || benchmarkReport.fps !== 62.5
) {{
  throw new Error("on-demand canvas benchmark contract");
}}
const mirroredManifest = {{
  fallback: "fallback.unknown",
  sprites: {{
    "entity.human.trader": {{x: 1, y: 1, auto_mirror: true}},
    "fallback.unknown": {{x: 0, y: 0}}
  }}
}};
const westSprite = client.resolveEntitySprite(
  mirroredManifest, {{render_key: "entity.human.trader", direction: "west"}},
  "idle", 0, false
);
const eastSprite = client.resolveEntitySprite(
  mirroredManifest, {{render_key: "entity.human.trader", direction: "east"}},
  "idle", 0, false
);
if (!westSprite.flip_x || eastSprite.flip_x || mirroredManifest.sprites["entity.human.trader"].flip_x) {{
  throw new Error("directional mirror fallback contract");
}}
"""
        completed = subprocess.run(
            [executable, "--input-type=module", "--eval", program],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_bind_is_loopback_only(self):
        for address in ("127.0.0.1", "::1", "localhost"):
            self.assertEqual(validate_web_bind(address), address)
        for address in ("0.0.0.0", "192.168.1.8", "example.com"):
            with self.assertRaises(ValueError):
                validate_web_bind(address)

    def test_server_module_has_no_eager_aiohttp_or_terminal_import(self):
        tree = ast.parse(
            (ROOT / "core/web_server.py").read_text(encoding="utf-8")
        )
        eager = {
            alias.name.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        eager.update(
            node.module.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module
        )
        self.assertNotIn("aiohttp", eager)
        self.assertNotIn("render", eager)


class FakeArchiveReader:
    def __init__(self):
        self.manifest = {
            "format": "chartographist-archive",
            "version": 1,
            "presentation_schema_version": 1,
            "world": {
                "name": "Archived World",
                "seed": 42,
                "width": 2,
                "height": 1,
            },
            "revisions": {
                "first": 2,
                "last": 5,
                "keyframe_interval": 60,
            },
            "capabilities": ["deltas", "snapshots"],
            "members": [],
        }
        self.snapshot_revisions = []
        self.timeline_queries = []
        self.comparisons = []

    def bounds(self):
        return {
            "first_revision": 2,
            "last_revision": 5,
            "first_cycle": 7,
            "last_cycle": 10,
        }

    def snapshot_at_revision(self, revision):
        if revision < 2 or revision > 5:
            from core.history_archive import ArchiveFormatError
            raise ArchiveFormatError("revision_out_of_bounds")
        self.snapshot_revisions.append(revision)
        return {
            "schema_version": 1,
            "revision": revision,
            "cycle": revision + 5,
            "world": self.manifest["world"],
            "cells": [],
            "panels": {},
        }

    def snapshot_at_cycle(self, cycle):
        if cycle < 7 or cycle > 10:
            from core.history_archive import ArchiveFormatError
            raise ArchiveFormatError("cycle_out_of_bounds")
        return self.snapshot_at_revision(cycle - 5)

    def timeline_events(self, **query):
        self.timeline_queries.append(query)
        return [{"chronicle_id": "event-8", "cycle": 8}]

    def compare(self, from_revision, to_revision):
        self.comparisons.append((from_revision, to_revision))
        return {
            "from_revision": from_revision,
            "to_revision": to_revision,
            "changed_cells": [],
        }


class ArchiveWebServerContractTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        Translator.load("fr")
        self.reader = FakeArchiveReader()
        self.client = TestClient(
            TestServer(create_archive_web_app(self.reader))
        )
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def test_archive_meta_snapshot_timeline_and_comparison(self):
        response = await self.client.get("/api/v1/meta")
        meta = await response.json()
        self.assertEqual(response.status, 200)
        self.assertEqual(meta["mode"], "archive")
        self.assertEqual(meta["language"], "fr")
        self.assertEqual(meta["labels"]["archive_mode"], "Archive")
        self.assertTrue(any(
            item["id"] == "interwoven" for item in meta["tilesets"]
        ))
        self.assertTrue(meta["archive"]["read_only"])
        self.assertEqual(meta["archive"]["last_revision"], 5)
        self.assertNotIn("commands", meta["capabilities"])

        response = await self.client.get("/api/v1/snapshot")
        self.assertEqual((await response.json())["revision"], 5)
        response = await self.client.get("/api/v1/snapshot?revision=3")
        self.assertEqual((await response.json())["revision"], 3)
        response = await self.client.get("/api/v1/snapshot?cycle=8")
        self.assertEqual((await response.json())["cycle"], 8)

        response = await self.client.get(
            "/api/v1/timeline?start_cycle=8&end_cycle=10&limit=12"
        )
        self.assertEqual((await response.json())["events"][0]["cycle"], 8)
        self.assertEqual(
            self.reader.timeline_queries[-1],
            {"start_cycle": 8, "end_cycle": 10, "limit": 12},
        )

        response = await self.client.get(
            "/api/v1/compare?from_revision=2&to_revision=5"
        )
        self.assertEqual((await response.json())["to_revision"], 5)
        self.assertEqual(self.reader.comparisons, [(2, 5)])

    async def test_archive_serves_browser_and_tileset_assets(self):
        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertIn('id="archive-controls"', await response.text())

        response = await self.client.get("/assets/app.js")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "application/javascript")

        response = await self.client.get("/api/v1/tilesets/interwoven")
        self.assertEqual(response.status, 200)
        manifest = await response.json()
        response = await self.client.get(manifest["sheet_urls"]["ocean"])
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")

    async def test_archive_api_rejects_invalid_or_mutating_requests(self):
        for path, status in (
            ("/api/v1/snapshot?revision=99", 404),
            ("/api/v1/timeline?limit=invalid", 400),
            ("/api/v1/compare?from_revision=2", 400),
            ("/api/v1/snapshot?revision=3&unexpected=true", 400),
            ("/api/v1/snapshot?revision=3&cycle=8", 400),
        ):
            response = await self.client.get(path)
            self.assertEqual(response.status, status, path)

        response = await self.client.post(
            "/api/v1/commands", json={"command": "pause"}
        )
        self.assertEqual(response.status, 403)
        self.assertEqual((await response.json())["error"], "archive_read_only")

        response = await self.client.get(
            "/api/v1/snapshot", headers={"Origin": "https://hostile.example"}
        )
        self.assertEqual(response.status, 403)

        response = await self.client.post(
            "/api/v1/commands",
            data=b"x" * (65 * 1024),
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status, 413)

    async def test_archive_api_integrates_with_the_real_headless_reader(self):
        from core.history_archive import (
            HistoryArchiveReader,
            HistoryArchiveRecorder,
        )

        def snapshot(revision, cycle, terrain, chronicles):
            return {
                "schema_version": 1,
                "revision": revision,
                "cycle": cycle,
                "clock": {"year": 1, "month": cycle},
                "world": {
                    "name": "Integration",
                    "seed": 81,
                    "width": 2,
                    "height": 1,
                },
                "cells": [
                    {"x": 0, "y": 0, "terrain_key": terrain},
                    {"x": 1, "y": 0, "terrain_key": "sand"},
                ],
                "logs": [],
                "panels": {"chronicles": chronicles},
            }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "integration.chartarchive"
            recorder = HistoryArchiveRecorder(path)
            recorder.record(snapshot(
                1,
                7,
                "grassland",
                [{"chronicle_id": "origin", "cycle": 7}],
            ))
            recorder.record(snapshot(
                2,
                8,
                "forest",
                [
                    {"chronicle_id": "origin", "cycle": 7},
                    {"chronicle_id": "forest", "cycle": 8},
                ],
            ))
            recorder.finalize()

            client = TestClient(TestServer(
                create_archive_web_app(HistoryArchiveReader(path))
            ))
            await client.start_server()
            try:
                response = await client.get("/api/v1/snapshot?revision=2")
                state = await response.json()
                self.assertEqual(state["cells"][0]["terrain_key"], "forest")

                response = await client.get(
                    "/api/v1/compare?from_revision=1&to_revision=2"
                )
                self.assertEqual(
                    (await response.json())["changed_cell_count"],
                    1,
                )

                response = await client.get(
                    "/api/v1/timeline?start_cycle=8&end_cycle=8"
                )
                events = (await response.json())["events"]
                self.assertEqual(
                    [event["chronicle_id"] for event in events],
                    ["forest"],
                )
            finally:
                await client.close()

    def test_archive_runner_loads_one_file_and_enforces_loopback(self):
        with (
            mock.patch(
                "core.history_archive.HistoryArchiveReader"
            ) as reader_type,
            mock.patch("aiohttp.web.run_app") as run_app,
        ):
            run_archive_web_server(
                "history.chartarchive",
                address="localhost",
                port=9017,
            )
        reader_type.assert_called_once_with("history.chartarchive")
        self.assertEqual(run_app.call_args.kwargs["host"], "localhost")
        self.assertEqual(run_app.call_args.kwargs["port"], 9017)

        with self.assertRaises(ValueError):
            run_archive_web_server(
                "history.chartarchive", address="0.0.0.0"
            )


class WebLaunchOptionTests(unittest.TestCase):
    def test_cli_exposes_optional_web_mode(self):
        argv = [
            "chartographist", "--seed", "7", "--renderer", "web",
            "--host", "localhost", "--port", "9016", "--tick-speed", "0.4",
            "--width", "120", "--height", "60",
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("core.system.Translator.load"),
            mock.patch("core.system.culture.load_config", return_value={}),
        ):
            options = load_launch_options()
        self.assertEqual(options.renderer, "web")
        self.assertEqual(options.web_host, "localhost")
        self.assertEqual(options.web_port, 9016)
        self.assertEqual(options.tick_speed, 0.4)
        self.assertEqual(options.width, 120)
        self.assertEqual(options.height, 60)

    def test_cli_opens_archive_without_loading_world_configuration(self):
        argv = [
            "chartographist", "--archive", "history.chartarchive",
            "--host", "localhost", "--port", "9017",
        ]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch("core.system.Translator.load"),
            mock.patch("core.system.culture.load_config") as load_config,
            mock.patch("core.system.random.randint") as random_seed,
        ):
            options = load_launch_options()
        self.assertEqual(options.archive_path, "history.chartarchive")
        self.assertIsNone(options.archive_record_path)
        self.assertEqual(options.seed, 0)
        self.assertEqual(options.renderer, "web")
        self.assertEqual(options.config, {})
        load_config.assert_not_called()
        random_seed.assert_not_called()

    def test_cli_records_archive_and_rejects_incoherent_archive_options(self):
        with (
            mock.patch.object(
                sys,
                "argv",
                ["chartographist", "--seed", "7", "--record-archive", "run.chartarchive"],
            ),
            mock.patch("core.system.Translator.load"),
            mock.patch("core.system.culture.load_config", return_value={}),
        ):
            options = load_launch_options()
        self.assertEqual(options.archive_record_path, "run.chartarchive")
        self.assertEqual(options.renderer, "web")

        invalid_arguments = (
            ("--archive", "read.chartarchive", "--record-archive", "write.chartarchive"),
            ("--archive", "read.chartarchive", "--load", "world.chart"),
            ("--archive", "read.chartarchive", "--save", "world.chart"),
            ("--archive", "read.chartarchive", "--scenario", "scenario.json"),
            ("--archive", "read.chartarchive", "--mod", "mod.json"),
            ("--archive", "read.chartarchive", "--renderer", "terminal"),
            ("--record-archive", "write.chartarchive", "--renderer", "terminal"),
        )
        for arguments in invalid_arguments:
            with (
                self.subTest(arguments=arguments),
                mock.patch.object(sys, "argv", ["chartographist", *arguments]),
                mock.patch("core.system.Translator.load"),
                mock.patch("core.system.culture.load_config", return_value={}),
                mock.patch("sys.stderr"),
                self.assertRaises(SystemExit),
            ):
                load_launch_options()

    def test_main_dispatches_archive_without_initializing_simulation(self):
        import main as application

        options = SimpleNamespace(archive_path="history.chartarchive", renderer="web")
        with (
            mock.patch.object(application.core, "load_launch_options", return_value=options),
            mock.patch.object(application.core, "init_terminal") as terminal,
            mock.patch.object(application, "_run_archive_mode") as archive_mode,
            mock.patch.object(application, "_run_web_mode") as web_mode,
        ):
            application.main()
        terminal.assert_not_called()
        web_mode.assert_not_called()
        archive_mode.assert_called_once_with(options)


    def test_cli_rejects_invalid_web_port_and_tick_speed(self):
        invalid_arguments = (
            ("--port", "0"),
            ("--port", "70000"),
            ("--tick-speed", "0"),
            ("--tick-speed", "11"),
            ("--width", "0"),
            ("--width", "241"),
            ("--height", "0"),
            ("--height", "121"),
        )
        for option, value in invalid_arguments:
            with (
                self.subTest(option=option, value=value),
                mock.patch.object(
                    sys,
                    "argv",
                    ["chartographist", "--seed", "7", option, value],
                ),
                mock.patch("core.system.Translator.load"),
                mock.patch("core.system.culture.load_config", return_value={}),
                mock.patch("sys.stderr"),
                self.assertRaises(SystemExit),
            ):
                load_launch_options()
    def test_main_dispatches_web_without_initializing_terminal(self):
        import main as application

        options = SimpleNamespace(renderer="web")
        with (
            mock.patch.object(
                application.core, "load_launch_options", return_value=options
            ),
            mock.patch.object(application.core, "init_terminal") as terminal,
            mock.patch.object(application, "_run_web_mode") as web_mode,
        ):
            application.main()
        terminal.assert_not_called()
        web_mode.assert_called_once_with(options)

    def test_web_mode_records_and_finalizes_archive(self):
        import main as application

        engine = mock.Mock(config={}, stats={"logs": []})
        options = SimpleNamespace(
            archive_record_path="run.chartarchive",
            config={},
            load_path=None,
            save_path=None,
            seed=7,
            width=120,
            height=60,
            tick_speed=0.15,
            web_host="localhost",
            web_port=9016,
        )
        recorder = mock.Mock()
        with (
            mock.patch.object(
                application.SimulationEngine,
                "create",
                return_value=engine,
            ) as create,
            mock.patch.object(application, "SimulationHost") as host_type,
            mock.patch(
                "core.history_archive.HistoryArchiveRecorder",
                return_value=recorder,
            ),
            mock.patch("core.web_server.run_web_server"),
            mock.patch("builtins.print"),
        ):
            application._run_web_mode(options)
        create.assert_called_once_with({}, 7, 120, 60)
        consumers = host_type.call_args.kwargs["snapshot_consumers"]
        self.assertEqual(len(consumers), 1)
        self.assertEqual(consumers[0], recorder.record)
        recorder.finalize.assert_called_once_with()
        recorder.abort.assert_not_called()

    def test_readme_documents_archive_creation_opening_and_trust_boundary(self):
        documentation = (ROOT / "README.md").read_bytes().decode("utf-8", errors="replace")
        for fragment in (
            "--record-archive world-history.chartarchive",
            "--archive world-history.chartarchive",
            "read-only",
            "untrusted",
            "Ctrl+C",
        ):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, documentation)


if __name__ == "__main__":
    unittest.main()
