"""aiohttp webapp hosted inside the Discord bot process."""

import json
import os
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import aiohttp
import discord
import logfire
from aiohttp import web

from . import auth, keys
from .gigs.routes import register as register_gigs
from .shop import register as register_shop

STATIC_DIR = Path(__file__).parent / "static"
LEGACY_DIR = STATIC_DIR / "legacy"

# Legacy static pages, kept reachable at the URLs they always had. /legacy/ maps to
# the old launcher index, because nginx used to serve it via its `index` directive.
LEGACY_PAGES = {
    "/go.html": "go.html",
    "/tictactoe.html": "tictactoe.html",
    "/legacy/": "index.html",
}


async def _oauth_http(app: web.Application) -> AsyncIterator[None]:
    async with aiohttp.ClientSession() as session:
        app[keys.HTTP_KEY] = session
        yield


async def _healthz(request: web.Request) -> web.StreamResponse:
    return web.json_response({"status": "ok"})


def _legacy_handler(filename: str) -> Callable[[web.Request], Awaitable[web.StreamResponse]]:
    """Build a handler serving one fixed legacy file. The name comes from the route table."""

    async def handler(request: web.Request) -> web.StreamResponse:
        return web.FileResponse(LEGACY_DIR / filename)

    return handler


async def _index(request: web.Request) -> web.StreamResponse:
    auth_config = request.app[auth.AUTH_KEY]
    user_id = auth.verify_session(auth_config, request)
    if user_id is None:
        # Also the Discord Activity entry point: activity.js detects the iframe and
        # swaps the plain login link for an SDK sign-in, which is the only kind that
        # works there.
        body = (
            "<!doctype html><html><head><title>Clockwork</title>"
            "<link rel='stylesheet' href='/static/shop.css'></head><body>"
            "<h1>Clockwork</h1>"
            "<p class='activity-status' id='activity-status'>Not logged in.</p>"
            "<p><a href='/auth/login'>Log in with Discord</a></p>"
            "<script>window.WEBAPP = __CONFIG__;</script>"
            "<script type='module' src='/static/activity.js'></script>"
            "</body></html>"
        ).replace("__CONFIG__", json.dumps({"client_id": auth_config.client_id}).replace("<", "\\u003c"))
    else:
        body = (
            f"<!doctype html><html><head><title>Clockwork</title></head><body>"
            f"<h1>Clockwork</h1><p>Logged in as <b>{user_id}</b>.</p>"
            f"<p><a href='/shop'>Shop</a> &middot; <a href='/credits'>Credits</a> "
            f"&middot; <a href='/auth/logout'>Log out</a></p>"
            f"</body></html>"
        )
    return web.Response(text=body, content_type="text/html")


def create_app() -> web.Application:
    app = web.Application(middlewares=[auth.require_session])
    app[auth.AUTH_KEY] = auth.AuthConfig.from_env()
    app.cleanup_ctx.append(_oauth_http)
    app.router.add_get("/healthz", _healthz)
    app.router.add_get("/", _index)
    app.router.add_get("/auth/login", auth.login_handler)
    app.router.add_get("/auth/callback", auth.callback_handler)
    app.router.add_get("/auth/logout", auth.logout_handler)
    app.router.add_post("/auth/exchange", auth.exchange_handler)
    app.router.add_static("/static/", STATIC_DIR)
    for path, filename in LEGACY_PAGES.items():
        app.router.add_get(path, _legacy_handler(filename))
    app.router.add_static("/legacy/", LEGACY_DIR)
    register_shop(app)
    register_gigs(app)
    return app


async def start_webapp(bot: discord.Client) -> web.AppRunner:
    app = create_app()
    app[keys.BOT_KEY] = bot

    auth_config = app[auth.AUTH_KEY]
    if not auth_config.configured:
        logfire.warning(
            f"Webapp auth not configured; missing: {', '.join(auth_config.missing_fields)}. "
            "Login will return 503 until set."
        )

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("WEBAPP_PORT", "8090"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logfire.info(f"Webapp listening on 0.0.0.0:{port}")
    return runner


async def stop_webapp(runner: web.AppRunner) -> None:
    await runner.cleanup()
