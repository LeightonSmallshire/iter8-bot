"""aiohttp webapp hosted inside the Discord bot process."""

import os
from collections.abc import AsyncIterator
from pathlib import Path

import aiohttp
import discord
import logfire
from aiohttp import web

from . import auth, keys
from .gigs.routes import register as register_gigs
from .shop import register as register_shop

STATIC_DIR = Path(__file__).parent / "static"


async def _oauth_http(app: web.Application) -> AsyncIterator[None]:
    async with aiohttp.ClientSession() as session:
        app[keys.HTTP_KEY] = session
        yield


async def _healthz(request: web.Request) -> web.StreamResponse:
    return web.json_response({"status": "ok"})


async def _index(request: web.Request) -> web.StreamResponse:
    auth_config = request.app[auth.AUTH_KEY]
    user_id = auth.verify_session(auth_config, request)
    if user_id is None:
        body = (
            "<!doctype html><html><head><title>Clockwork</title></head><body>"
            "<h1>Clockwork</h1><p>Not logged in.</p>"
            "<p><a href='/auth/login'>Log in with Discord</a></p>"
            "</body></html>"
        )
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
    app.router.add_static("/static/", STATIC_DIR)
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
