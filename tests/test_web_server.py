import base64
import ast
from pathlib import Path
import sys
import shutil
import subprocess
import unittest
from types import SimpleNamespace
from unittest import mock

from aiohttp.test_utils import TestClient, TestServer

from core.translator import Translator
from core.system import load_launch_options
from core.web_server import _publish_cycles, create_web_app, validate_web_bind


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
        self.assertEqual(meta["presentation_schema_version"], 1)
        self.assertEqual(meta["world"]["name"], "Web Test")
        self.assertEqual(meta["language"], "fr")
        self.assertEqual(meta["labels"]["pause"], "Pause")
        self.assertEqual(
            meta["labels"]["simulation_controls"], "Contrôles de simulation"
        )
        self.assertEqual(meta["labels"]["render_mode"], "Rendu")
        self.assertEqual(meta["tilesets"][0]["id"], "classic")
        self.assertEqual(
            meta["tilesets"][0]["manifest_url"],
            "/api/v1/tilesets/classic",
        )
        interwoven = next(
            item for item in meta["tilesets"] if item["id"] == "interwoven"
        )
        self.assertEqual(interwoven["name"], "Chartographist Entrelacé")
        self.assertIn("websocket", meta["capabilities"])
        self.assertIn("spritesheets", meta["capabilities"])

        response = await self.client.get("/api/v1/snapshot")
        self.assertEqual(await response.json(), self.host.snapshot())

        response = await self.client.get("/")
        self.assertEqual(response.status, 200)
        self.assertTrue(response.content_type.startswith("text/html"))
        self.assertIn("Chartographist", await response.text())

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
        response = await self.client.get("/api/v1/tilesets/classic")
        self.assertEqual(response.status, 200)
        self.assertEqual((await response.json())["id"], "classic")
        response = await self.client.get(
            "/assets/tilesets/classic/atlas.png"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        response = await self.client.get("/api/v1/tilesets/interwoven")
        self.assertEqual(response.status, 200)
        interwoven = await response.json()
        self.assertEqual(interwoven["id"], "interwoven")
        self.assertEqual(interwoven["tile_width"], interwoven["tile_height"])
        self.assertEqual(interwoven["edge_blending"]["mode"], "interlaced")
        response = await self.client.get(
            "/assets/tilesets/interwoven/atlas.png"
        )
        self.assertEqual(response.status, 200)
        self.assertEqual(response.content_type, "image/png")
        response = await self.client.get("/api/v1/tilesets/unknown")
        self.assertEqual(response.status, 404)
        response = await self.client.get(
            "/assets/tilesets/classic/unknown.png"
        )
        self.assertEqual(response.status, 404)

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
            'id="selection"',
            'tabindex="0"',
            'aria-live="polite"',
            'data-i18n-aria="simulation_controls"',
            'data-i18n-aria="observatory"',
        ):
            self.assertIn(fragment, markup)
        self.assertNotIn('aria-label="Simulation"', markup)
        self.assertNotIn('aria-label="Observatory"', markup)
        for fragment in (
            "new WebSocket",
            "applyDeltaToSnapshot",
            "requestAnimationFrame",
            "addEventListener(\"wheel\"",
            "addEventListener(\"pointerdown\"",
            "addEventListener(\"keydown\"",
            "loadTileset",
            "resolveSpriteLayers",
            "edgeBlendProfile",
            "drawImage",
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
const cell = client.cellAtCanvasPoint(37, 19, {{
  offsetX: 1, offsetY: 1, zoom: 1, tileSize: 18
}});
if (cell.x !== 2 || cell.y !== 1) throw new Error("geometry contract");
const manifest = {{
  tile_width: 16,
  tile_height: 16,
  fallback: "fallback.unknown",
  sprites: {{
    "terrain.grassland": {{x: 1, y: 0}},
    "site.ruins": {{x: 2, y: 0}},
    "entity.animal.wolf": {{x: 3, y: 0}},
    "fallback.unknown": {{x: 0, y: 0}}
  }}
}};
const layers = client.resolveSpriteLayers({{
  terrain_key: "grassland",
  hydrology_key: "river",
  infrastructure_key: "road",
  site_key: "ruins.ancient",
  entity: {{render_key: "entity.animal.wolf"}}
}});
if (layers.join("|") !== "terrain.grassland|hydrology.river|infrastructure.road|site.ruins.ancient|entity.animal.wolf") {{
  throw new Error("layer contract");
}}
const siteSprite = client.resolveSprite(manifest, "site.ruins.ancient");
const fallbackSprite = client.resolveSprite(manifest, "mod.unknown");
if (siteSprite.x !== 2 || fallbackSprite.x !== 0) {{
  throw new Error("sprite fallback contract");
}}
const blendA = client.edgeBlendProfile(4, 7, "top", 0.18, 8);
const blendB = client.edgeBlendProfile(4, 7, "top", 0.18, 8);
const blendOther = client.edgeBlendProfile(5, 7, "top", 0.18, 8);
if (blendA.length !== 8 || JSON.stringify(blendA) !== JSON.stringify(blendB)) {{
  throw new Error("edge blend determinism contract");
}}
if (JSON.stringify(blendA) === JSON.stringify(blendOther)) {{
  throw new Error("edge blend spatial variation contract");
}}
if (blendA.some((value) => value <= 0 || value > 0.18)) {{
  throw new Error("edge blend bounds contract");
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


class WebLaunchOptionTests(unittest.TestCase):
    def test_cli_exposes_optional_web_mode(self):
        argv = [
            "chartographist", "--seed", "7", "--renderer", "web",
            "--host", "localhost", "--port", "9016", "--tick-speed", "0.4",
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


    def test_cli_rejects_invalid_web_port_and_tick_speed(self):
        invalid_arguments = (
            ("--port", "0"),
            ("--port", "70000"),
            ("--tick-speed", "0"),
            ("--tick-speed", "11"),
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


if __name__ == "__main__":
    unittest.main()
