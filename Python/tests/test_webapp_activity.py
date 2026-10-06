"""Tests for the Discord Activity sign-in path in webapp.auth.

Covers POST /auth/exchange, which the Embedded App SDK calls from inside Discord's frame
with a bearer access token, plus the cookie attributes that let the resulting session
survive that cross-site context.
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
from conftest import (
    FakeResponse,
    http_of,
    make_auth_app,
    stub_me_failure,
    stub_unreachable,
)

from utils import allowlist
from webapp import auth

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


def _stub_identity(app: object, user_id: int) -> None:
    """Let GET /users/@me succeed for the given user."""
    from unittest.mock import MagicMock

    http_of(app).get = MagicMock(return_value=FakeResponse(200, {"id": str(user_id)}))


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


# --- /auth/exchange ----------------------------------------------------------


async def test_exchange_sets_a_usable_session_cookie() -> None:
    app = make_auth_app(CONFIG)
    _stub_identity(app, ALLOWED_UID)

    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"access_token": "tok"})
        assert response.status == 200
        assert (await response.json())["ok"] is True

        cookie = response.headers.get("Set-Cookie", "")
        assert auth.SESSION_COOKIE in cookie
        assert "SameSite=None" in cookie
        assert "Secure" in cookie
        assert "HttpOnly" in cookie

        signed = response.cookies[auth.SESSION_COOKIE].value

    assert auth.verify_session(CONFIG, _cookie_request(signed)) == ALLOWED_UID


async def test_exchange_presents_the_token_as_a_bearer_credential() -> None:
    app = make_auth_app(CONFIG)
    _stub_identity(app, ALLOWED_UID)

    async with TestClient(TestServer(app)) as client:
        await client.post("/auth/exchange", json={"access_token": "tok"})

    get = http_of(app).get
    get.assert_called_once()
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer tok"
    # v2 hands us a token, so there is no authorization code to exchange: the token
    # endpoint must never be touched.
    http_of(app).post.assert_not_called()


@pytest.mark.parametrize(
    "payload",
    [{}, {"access_token": ""}, {"access_token": "   "}, {"access_token": 42}, {"access_token": None}],
)
async def test_exchange_rejects_a_bad_token(payload: dict[str, object]) -> None:
    app = make_auth_app(CONFIG)
    _stub_identity(app, ALLOWED_UID)

    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json=payload)).status == 400


async def test_exchange_rejects_a_non_json_body() -> None:
    app = make_auth_app(CONFIG)
    _stub_identity(app, ALLOWED_UID)

    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", data="not json", headers={"Content-Type": "text/plain"})
        assert response.status == 400


async def test_exchange_rejects_a_non_allowlisted_user() -> None:
    app = make_auth_app(CONFIG)
    _stub_identity(app, DENIED_UID)

    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"access_token": "tok"})
        assert response.status == 403
        assert auth.SESSION_COOKIE not in "\n".join(response.headers.getall("Set-Cookie", []))


async def test_exchange_refuses_a_token_discord_rejects() -> None:
    """A forged or expired token must not produce a session."""
    app = make_auth_app(CONFIG)
    from unittest.mock import MagicMock

    http_of(app).get = MagicMock(return_value=FakeResponse(401, {"message": "401: Unauthorized"}))

    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"access_token": "forged"})
        assert response.status == 502
        assert auth.SESSION_COOKIE not in "\n".join(response.headers.getall("Set-Cookie", []))


async def test_exchange_surfaces_a_discord_outage_as_502() -> None:
    app = make_auth_app(CONFIG)
    stub_me_failure(app)

    async with TestClient(TestServer(app)) as client:
        response = await client.post("/auth/exchange", json={"access_token": "tok"})
        assert response.status == 502
        assert auth.SESSION_COOKIE not in "\n".join(response.headers.getall("Set-Cookie", []))


async def test_exchange_wraps_network_errors_as_502() -> None:
    app = make_auth_app(CONFIG)
    stub_unreachable(app)

    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json={"access_token": "tok"})).status == 502


async def test_exchange_503s_when_auth_is_unconfigured() -> None:
    app = make_auth_app(auth.AuthConfig(client_id="", client_secret="", base_url="", session_secret=""))

    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json={"access_token": "tok"})).status == 503


async def test_exchange_is_reachable_without_a_session() -> None:
    """Discord's frame must reach the endpoint before it holds any session."""
    app = make_auth_app(CONFIG, middleware=True)
    _stub_identity(app, ALLOWED_UID)

    async with TestClient(TestServer(app)) as client:
        assert (await client.post("/auth/exchange", json={"access_token": "tok"})).status == 200
