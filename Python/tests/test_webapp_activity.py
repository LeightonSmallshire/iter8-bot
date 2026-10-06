"""Tests for the Discord Activity sign-in path in webapp.auth.

Covers the /auth/exchange endpoint the Embedded App SDK hands an authorization code to,
plus the cookie attributes that let a session survive Discord's cross-site iframe.
"""

from typing import Any, cast
from unittest.mock import MagicMock

import aiohttp
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from utils import allowlist
from webapp import auth, keys

ALLOWED_UID = next(iter(allowlist.ALLOWED_IDS))
DENIED_UID = next(uid for uid in range(1, 10_000_000) if not allowlist.is_allowed(uid))

CONFIG = auth.AuthConfig(
    client_id="cid",
    client_secret="secret",
    base_url="https://trejon.smallshire.co.uk",
    session_secret="session-secret",
)

LOCAL_CONFIG = auth.AuthConfig(
    client_id="cid",
    client_secret="secret",
    base_url="http://localhost:8090",
    session_secret="session-secret",
)


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


def _app(config: auth.AuthConfig = CONFIG, middleware: bool = False) -> web.Application:
    app: web.Application = web.Application(middlewares=[auth.require_session] if middleware else [])
    app[auth.AUTH_KEY] = config
    app[keys.HTTP_KEY] = cast("aiohttp.ClientSession", MagicMock(spec=aiohttp.ClientSession))
    app.router.add_post("/auth/exchange", auth.exchange_handler)
    return app


def _http(app: web.Application) -> Any:
    value: Any = app[keys.HTTP_KEY]
    return value


def _stub_discord(app: web.Application, user_id: int) -> None:
    """Make both the token exchange and the /users/@me call succeed."""
    _http(app).post = MagicMock(return_value=FakeResponse(200, {"access_token": "at"}))
    _http(app).get = MagicMock(return_value=FakeResponse(200, {"id": str(user_id)}))


def _cookie_request(value: str) -> web.Request:
    return make_mocked_request("GET", "/shop", headers={"Cookie": f"{auth.SESSION_COOKIE}={value}"})


# --- cookie attributes -------------------------------------------------------


def test_same_site_is_none_over_https_for_the_activity_iframe() -> None:
    # Lax cookies are never sent to our origin from inside Discord's cross-site frame.
    assert CONFIG.same_site == "None"
    assert CONFIG.secure_cookies is True


def test_same_site_stays_lax_for_local_http_dev() -> None:
    # Browsers reject SameSite=None without Secure, so plain-http dev must keep Lax.
    assert LOCAL_CONFIG.same_site == "Lax"
    assert LOCAL_CONFIG.secure_cookies is False


def test_activity_redirect_uri_defaults_to_base_url() -> None:
    assert CONFIG.activity_redirect_uri == "https://trejon.smallshire.co.uk"


def test_activity_redirect_uri_is_overridable_and_strips_trailing_slash() -> None:
    config = auth.AuthConfig(
        client_id="cid",
        client_secret="secret",
        base_url="https://example.test/",
        session_secret="s",
        activity_url="https://example.test/activity/",
    )
    assert config.activity_redirect_uri == "https://example.test/activity"


# --- /auth/exchange ----------------------------------------------------------


async def test_exchange_sets_a_usable_session_cookie() -> None:
    app = _app()
    _stub_discord(app, ALLOWED_UID)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"code": "abc"})
        assert response.status == 200
        assert (await response.json())["ok"] is True

        cookie = response.headers.get("Set-Cookie", "")
        assert auth.SESSION_COOKIE in cookie
        assert "SameSite=None" in cookie
        assert "Secure" in cookie
        assert "HttpOnly" in cookie

        signed = response.cookies[auth.SESSION_COOKIE].value

    assert auth.verify_session(CONFIG, _cookie_request(signed)) == ALLOWED_UID


async def test_exchange_posts_the_activity_redirect_uri() -> None:
    app = _app()
    _stub_discord(app, ALLOWED_UID)
    async with TestClient(TestServer(app)) as client:
        await client.post("/auth/exchange", json={"code": "abc"})

    post = _http(app).post
    post.assert_called_once()
    form = post.call_args.kwargs["data"]
    assert form["grant_type"] == "authorization_code"
    assert form["code"] == "abc"
    assert form["redirect_uri"] == "https://trejon.smallshire.co.uk"


@pytest.mark.parametrize("payload", [{}, {"code": ""}, {"code": "   "}, {"code": 42}, {"code": None}])
async def test_exchange_rejects_a_bad_code(payload: dict[str, object]) -> None:
    app = _app()
    _stub_discord(app, ALLOWED_UID)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json=payload)).status == 400


async def test_exchange_rejects_a_non_json_body() -> None:
    app = _app()
    _stub_discord(app, ALLOWED_UID)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", data="not json", headers={"Content-Type": "text/plain"})
        assert response.status == 400


async def test_exchange_rejects_a_non_allowlisted_user() -> None:
    app = _app()
    _stub_discord(app, DENIED_UID)
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"code": "abc"})
        assert response.status == 403
        assert auth.SESSION_COOKIE not in response.headers.get("Set-Cookie", "")


async def test_exchange_surfaces_a_discord_token_failure() -> None:
    app = _app()
    _http(app).post = MagicMock(return_value=FakeResponse(400, {"error": "invalid_grant"}))
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"code": "abc"})
        assert response.status == 502
        assert auth.SESSION_COOKIE not in response.headers.get("Set-Cookie", "")


async def test_exchange_503s_when_auth_is_unconfigured() -> None:
    app = _app(auth.AuthConfig(client_id="", client_secret="", base_url="", session_secret=""))
    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json={"code": "abc"})).status == 503


async def test_exchange_is_reachable_without_a_session() -> None:
    """Discord's frame must reach the endpoint before it holds any session."""
    app = _app(middleware=True)
    _stub_discord(app, ALLOWED_UID)
    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json={"code": "abc"})).status == 200
