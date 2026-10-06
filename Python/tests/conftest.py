"""Shared test helpers for the webapp's Discord authentication flows."""

from typing import Any, cast
from unittest.mock import MagicMock

import aiohttp
from aiohttp import web

from webapp import auth, keys


class FakeResponse:
    """Stand-in for the async context manager aiohttp returns from a request."""

    def __init__(self, status: int, payload: object) -> None:
        self.status = status
        self._payload = payload

    async def json(self, content_type: str | None = None) -> object:
        del content_type
        return self._payload

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        return None


def make_auth_app(
    config: auth.AuthConfig,
    routes: bool = True,
    middleware: bool = False,
) -> web.Application:
    """An app wired the way ``create_app`` wires it, for the given auth config."""
    app: web.Application = web.Application(middlewares=[auth.require_session] if middleware else [])
    app[auth.AUTH_KEY] = config
    app[keys.HTTP_KEY] = cast("aiohttp.ClientSession", MagicMock(spec=aiohttp.ClientSession))
    if routes:
        app.router.add_get("/auth/login", auth.login_handler)
        app.router.add_get("/auth/callback", auth.callback_handler)
        app.router.add_get("/auth/logout", auth.logout_handler)
        app.router.add_post("/auth/exchange", auth.exchange_handler)
    return app


def http_of(app: web.Application) -> Any:
    """The mocked aiohttp session stored on the app."""
    value: Any = app[keys.HTTP_KEY]
    return value


def stub_discord(app: web.Application, user_id: int) -> None:
    """Make both the token exchange and the ``/users/@me`` call succeed."""
    http_of(app).post = MagicMock(return_value=FakeResponse(200, {"access_token": "at"}))
    http_of(app).get = MagicMock(return_value=FakeResponse(200, {"id": str(user_id)}))


def stub_token_failure(app: web.Application, status: int = 400) -> None:
    """Make the token exchange fail, as Discord does for a bogus code."""
    http_of(app).post = MagicMock(return_value=FakeResponse(status, {"error": "invalid_grant"}))


def stub_me_failure(app: web.Application, status: int = 500) -> None:
    """Let the token exchange succeed but the identity lookup fail."""
    http_of(app).post = MagicMock(return_value=FakeResponse(200, {"access_token": "at"}))
    http_of(app).get = MagicMock(return_value=FakeResponse(status, {}))


def stub_unreachable(app: web.Application) -> None:
    """Make the HTTP session itself raise, as it would with no network."""
    http_of(app).post = MagicMock(side_effect=aiohttp.ClientError("boom"))
