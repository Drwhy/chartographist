"""Serveur HTTP local optionnel pour le contrat de présentation v1."""

import asyncio
from contextlib import suppress
import ipaddress
from pathlib import Path
from urllib.parse import urlsplit

from core.presentation import PRESENTATION_SCHEMA_VERSION, _json_value, snapshot_delta
from core.tilesets import discover_tilesets
from core.translator import Translator


API_VERSION = 1
_DEFAULT_CLIENT_MAX_SIZE = 64 * 1024
_DEFAULT_STATIC_ROOT = Path(__file__).resolve().parents[1] / "web"
_STATIC_ASSETS = {
    "app.js": "application/javascript",
    "styles.css": "text/css",
}
_WEB_LABEL_KEYS = (
    "simulation_controls",
    "observatory",
    "render_mode",
    "glyph_theme",
    "sprite_theme",
    "connection_connecting",
    "connection_connected",
    "connection_disconnected",
    "year",
    "month",
    "cycle",
    "pause",
    "resume",
    "step",
    "speed",
    "logs",
    "systems",
    "chronicles",
    "diplomacy",
    "why",
    "selection",
    "no_selection",
    "terrain",
    "entity",
    "map",
    "overview",
    "sites",
    "artifacts",
    "politics",
    "territory",
    "migration",
    "warfare",
    "peace",
    "economy",
    "climate",
)


def validate_web_bind(address):
    """Refuse toute écoute non locale dans le premier protocole web."""
    value = str(address).strip()
    if value.lower() == "localhost":
        return value
    try:
        if ipaddress.ip_address(value).is_loopback:
            return value
    except ValueError:
        pass
    raise ValueError("web server address must be loopback-only")


def create_web_app(
    host,
    *,
    static_root=None,
    client_max_size=_DEFAULT_CLIENT_MAX_SIZE,
    drive_simulation=False,
):
    """Construit l'application sans importer aiohttp en mode terminal."""
    from aiohttp import WSMsgType, web

    root = Path(static_root) if static_root is not None else _DEFAULT_STATIC_ROOT
    tilesets = {
        manifest["id"]: manifest
        for manifest in discover_tilesets(root / "assets" / "tilesets")
    }
    sockets = set()

    @web.middleware
    async def local_origin_only(request, handler):
        origin = request.headers.get("Origin")
        if origin and not _is_local_origin(origin):
            return web.json_response({"error": "origin_not_allowed"}, status=403)
        return await handler(request)

    app = web.Application(
        client_max_size=int(client_max_size),
        middlewares=[local_origin_only],
    )

    async def meta(request):
        engine = host.engine
        stats = engine.stats
        config = engine.config
        tileset_summaries = [
            {
                "id": manifest["id"],
                "name": manifest["name"],
                "manifest_url": f"/api/v1/tilesets/{manifest['id']}",
                "license": manifest["license"],
            }
            for manifest in tilesets.values()
        ]
        return web.json_response({
            "api_version": API_VERSION,
            "language": Translator.current_language(),
            "labels": {
                key: Translator.translate(f"web.{key}") for key in _WEB_LABEL_KEYS
            },
            "presentation_schema_version": PRESENTATION_SCHEMA_VERSION,
            "world": {
                "name": str(config.get("world_name", "WORLD")),
                "seed": stats.get("seed"),
                "cycle": int(engine.world.get("cycle", 0)),
            },
            "runtime": {
                "revision": int(host.revision),
                "paused": bool(host.paused),
                "tick_interval": float(host.tick_interval),
                "scope": "single_world",
            },
            "tilesets": tileset_summaries,
            "capabilities": [
                "snapshot",
                "websocket",
                "commands",
                "entity_inspection",
                "spritesheets",
            ],
        })

    async def current_snapshot(request):
        return web.json_response(host.snapshot())

    async def inspect_entity(request):
        try:
            entity_id = int(request.match_info["entity_id"])
        except (TypeError, ValueError):
            raise web.HTTPNotFound()
        result = host.engine.inspect_entity(entity_id)
        if result is None:
            raise web.HTTPNotFound()
        return web.json_response(_json_value(result))

    async def submit_command(request):
        payload = await _request_json(request, web)
        accepted = _submit_payload(host, payload)
        if not accepted:
            return web.json_response({"error": "invalid_command"}, status=400)
        return web.json_response({"accepted": True}, status=202)

    async def stream(request):
        socket = web.WebSocketResponse(
            heartbeat=30.0,
            max_msg_size=int(client_max_size),
            compress=False,
        )
        await socket.prepare(request)
        sockets.add(socket)
        await socket.send_json({"type": "snapshot", "payload": host.snapshot()})
        try:
            async for message in socket:
                if message.type == WSMsgType.TEXT:
                    try:
                        payload = message.json()
                    except (TypeError, ValueError):
                        await socket.send_json({
                            "type": "command",
                            "accepted": False,
                        })
                        continue
                    accepted = _submit_payload(host, payload)
                    await socket.send_json({
                        "type": "command",
                        "accepted": accepted,
                    })
                elif message.type in {
                    WSMsgType.CLOSE,
                    WSMsgType.CLOSED,
                    WSMsgType.ERROR,
                }:
                    break
        finally:
            sockets.discard(socket)
        return socket

    async def index(request):
        path = root / "index.html"
        if not path.is_file():
            raise web.HTTPNotFound()
        return web.FileResponse(path)

    async def static_asset(request):
        name = request.match_info["name"]
        content_type = _STATIC_ASSETS.get(name)
        path = root / name
        if content_type is None or not path.is_file():
            raise web.HTTPNotFound()
        response = web.FileResponse(path)
        response.content_type = content_type
        return response

    async def tileset_manifest(request):
        identifier = request.match_info["tileset_id"]
        manifest = tilesets.get(identifier)
        if manifest is None:
            raise web.HTTPNotFound()
        return web.json_response({
            **manifest,
            "image_url": (
                f"/assets/tilesets/{identifier}/{manifest['image']}"
            ),
        })

    async def tileset_image(request):
        identifier = request.match_info["tileset_id"]
        name = request.match_info["name"]
        manifest = tilesets.get(identifier)
        if manifest is None or name != manifest["image"]:
            raise web.HTTPNotFound()
        path = root / "assets" / "tilesets" / identifier / name
        if not path.is_file():
            raise web.HTTPNotFound()
        response = web.FileResponse(path)
        response.content_type = "image/png"
        return response

    app.router.add_get("/", index)
    app.router.add_get("/assets/{name}", static_asset)
    app.router.add_get("/api/v1/tilesets/{tileset_id}", tileset_manifest)
    app.router.add_get(
        "/assets/tilesets/{tileset_id}/{name}",
        tileset_image,
    )
    app.router.add_get("/api/v1/meta", meta)
    app.router.add_get("/api/v1/snapshot", current_snapshot)
    app.router.add_get("/api/v1/entities/{entity_id}", inspect_entity)
    app.router.add_post("/api/v1/commands", submit_command)
    app.router.add_get("/api/v1/stream", stream)

    if drive_simulation:
        ticker_task = None

        async def start_ticker(application):
            nonlocal ticker_task
            ticker_task = asyncio.create_task(_publish_cycles(host, sockets))

        async def stop_ticker(application):
            if ticker_task is not None:
                ticker_task.cancel()
                with suppress(asyncio.CancelledError):
                    await ticker_task
            await _close_sockets(sockets)

        app.on_startup.append(start_ticker)
        app.on_cleanup.append(stop_ticker)
    else:
        async def close_only(application):
            await _close_sockets(sockets)

        app.on_cleanup.append(close_only)
    return app


def run_web_server(host, *, address="127.0.0.1", port=8765):
    """Lance le serveur et la cadence sur le thread propriétaire du moteur."""
    from aiohttp import web

    validated = validate_web_bind(address)
    app = create_web_app(host, drive_simulation=True)
    web.run_app(
        app,
        host=validated,
        port=int(port),
        print=None,
        handle_signals=True,
    )


async def _publish_cycles(host, sockets):
    previous = None
    while not host.stopped:
        await asyncio.sleep(host.tick_interval)
        if not sockets:
            host.tick(publish_snapshot=False)
            previous = None
            continue
        if previous is None:
            previous = host.snapshot()
        current = host.tick()
        if current.get("revision") == previous.get("revision"):
            continue
        presentation = host.engine.config.get("presentation", {})
        maximum = (
            presentation.get("max_delta_cells", 2048)
            if isinstance(presentation, dict) else 2048
        )
        delta = snapshot_delta(previous, current, max_changes=maximum)
        message = (
            {"type": "snapshot", "payload": current}
            if delta["resync"]
            else {"type": "delta", "payload": delta}
        )
        await _broadcast(sockets, message)
        previous = current


async def _broadcast(sockets, message):
    stale = []
    for socket in tuple(sockets):
        try:
            await socket.send_json(message)
        except (ConnectionError, RuntimeError):
            stale.append(socket)
    for socket in stale:
        sockets.discard(socket)


async def _close_sockets(sockets):
    for socket in tuple(sockets):
        with suppress(ConnectionError, RuntimeError):
            await socket.close()
    sockets.clear()


async def _request_json(request, web):
    try:
        payload = await request.json()
    except (ValueError, TypeError):
        raise web.HTTPBadRequest()
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest()
    return payload


def _submit_payload(host, payload):
    if not isinstance(payload, dict):
        return False
    if set(payload) - {"command", "value"}:
        return False
    command = payload.get("command")
    if not isinstance(command, str):
        return False
    return host.submit_command(command, payload.get("value"))


def _is_local_origin(origin):
    try:
        hostname = urlsplit(str(origin)).hostname
    except ValueError:
        return False
    if hostname is None:
        return False
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False
