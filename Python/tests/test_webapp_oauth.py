"""Tests for the classic Discord redirect login flow.

Covers ``login_handler``, ``callback_handler`` and ``logout_handler``. These three had no
coverage at all before the Activity work refactored the code-exchange step out of
``callback_handler`` into ``_discord_user_id``, which both flows now share.
"""

from typing import Any
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit

import aiohttp
import pytest
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request
from conftest import (
    FakeResponse,
    http_of,
    make_auth_app,
    stub_discord,
    stub_me_failure,
    stub_token_failure,
    stub_unreachable,
)

from utils import allowlist
from webapp import auth

ALLOWED_UID = next(iter(allowlist.ALLOWED_IDS))
DENIED_UID = next(uid for uid in range(1, 10_000_000) if not allowlist.is_allowed(uid))

HTTPS = auth.AuthConfig(
    client_id="cid",
    client_secret="secret",
    base_url="https://trejon.smallshire.co.uk",
    session_secret="session-secret",
)

LOCAL = auth.AuthConfig(
    client_id="cid",
    client_secret="secret",
    base_url="http://localhost:8090",
    session_secret="session-secret",
)

UNCONFIGURED = auth.AuthConfig(client_id="", client_secret="", base_url="", session_secret="")

STATE = "state-value"


async def _login(app: Any, next_path: str = "/shop") -> str:
    """Run the login leg and return the state Discord would be handed."""
    async with TestClient(TestServer(app)) as client:
        response = await client.get(f"/auth/login?next={next_path}", allow_redirects=False)
        assert response.status == 302
        location = response.headers["Location"]
        return location.split("state=")[-1].split("&")[0]


# --- login_handler -----------------------------------------------------------


async def test_login_redirects_to_discord_with_the_right_parameters() -> None:
    app = make_auth_app(HTTPS)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/auth/login?next=/gigs", allow_redirects=False)

    assert response.status == 302
    location = response.headers["Location"]
    assert location.startswith("https://discord.com/oauth2/authorize?")

    query = parse_qs(urlsplit(location).query)
    assert query["client_id"] == ["cid"]
    # aiohttp normalises the Location URL, so compare the decoded values.
    assert query["redirect_uri"] == ["https://trejon.smallshire.co.uk/auth/callback"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["identify"]
    assert query["state"]


async def test_login_sets_state_and_next_cookies_for_the_activity_context() -> None:
    app = make_auth_app(HTTPS)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/auth/login?next=/gigs", allow_redirects=False)

    cookies = response.headers.getall("Set-Cookie", [])
    joined = "\n".join(cookies)
    assert auth.STATE_COOKIE in joined
    assert auth.NEXT_COOKIE in joined
    # Lax cookies would be dropped in Discord's cross-site frame, so https must get None.
    assert "SameSite=None" in joined
    assert "HttpOnly" in joined
    assert "/gigs" in joined


async def test_login_keeps_lax_cookies_for_local_http_dev() -> None:
    app = make_auth_app(LOCAL)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/auth/login", allow_redirects=False)

    joined = "\n".join(response.headers.getall("Set-Cookie", []))
    assert "SameSite=Lax" in joined
    assert "SameSite=None" not in joined


@pytest.mark.parametrize("unsafe", ["//evil.example", "https://evil.example", "/shop\\..\\evil"])
async def test_login_refuses_to_remember_an_unsafe_next(unsafe: str) -> None:
    app = make_auth_app(HTTPS)
    async with TestClient(TestServer(app)) as client:
        response = await client.get(f"/auth/login?next={unsafe}", allow_redirects=False)

    joined = "\n".join(response.headers.getall("Set-Cookie", []))
    assert f"{auth.NEXT_COOKIE}=;" in joined or f'{auth.NEXT_COOKIE}="/"' in joined
    assert "evil" not in joined


async def test_login_503s_when_unconfigured() -> None:
    app = make_auth_app(UNCONFIGURED)
    async with TestClient(TestServer(app)) as client:
        assert (await client.get("/auth/login", allow_redirects=False)).status == 503


# --- callback_handler --------------------------------------------------------


async def _callback(
    app: Any,
    state: str | None = STATE,
    cookie_state: str | None = STATE,
    next_cookie: str | None = "/shop",
    code: str | None = "the-code",
) -> Any:
    cookies = []
    if cookie_state is not None:
        cookies.append(f"{auth.STATE_COOKIE}={cookie_state}")
    if next_cookie is not None:
        cookies.append(f"{auth.NEXT_COOKIE}={next_cookie}")
    query = []
    if state is not None:
        query.append(f"state={state}")
    if code is not None:
        query.append(f"code={code}")
    async with TestClient(TestServer(app)) as client:
        return await client.get(
            f"/auth/callback?{'&'.join(query)}",
            headers={"Cookie": "; ".join(cookies)},
            allow_redirects=False,
        )


async def test_callback_signs_the_user_in_and_redirects_to_next() -> None:
    app = make_auth_app(HTTPS)
    stub_discord(app, ALLOWED_UID)

    response = await _callback(app)
    assert response.status == 302
    assert response.headers["Location"] == "/shop"

    signed = response.cookies[auth.SESSION_COOKIE].value
    request = make_mocked_request("GET", "/shop", headers={"Cookie": f"{auth.SESSION_COOKIE}={signed}"})
    assert auth.verify_session(HTTPS, request) == ALLOWED_UID


async def test_callback_clears_the_state_and_next_cookies() -> None:
    app = make_auth_app(HTTPS)
    stub_discord(app, ALLOWED_UID)

    response = await _callback(app)
    cleared = "\n".join(response.headers.getall("Set-Cookie", []))
    assert f'{auth.STATE_COOKIE}=""' in cleared or f"{auth.STATE_COOKIE}=;" in cleared
    assert f'{auth.NEXT_COOKIE}=""' in cleared or f"{auth.NEXT_COOKIE}=;" in cleared


async def test_callback_uses_the_web_redirect_uri_not_the_activity_one() -> None:
    """The two flows differ only here; conflating them breaks one of them."""
    config = auth.AuthConfig(
        client_id="cid",
        client_secret="secret",
        base_url="https://trejon.smallshire.co.uk",
        session_secret="s",
        activity_url="https://elsewhere.test/activity",
    )
    app = make_auth_app(config)
    stub_discord(app, ALLOWED_UID)

    await _callback(app)

    form = http_of(app).post.call_args.kwargs["data"]
    assert form["redirect_uri"] == "https://trejon.smallshire.co.uk/auth/callback"


async def test_callback_falls_back_to_root_for_an_unsafe_next_cookie() -> None:
    app = make_auth_app(HTTPS)
    stub_discord(app, ALLOWED_UID)

    response = await _callback(app, next_cookie="//evil.example")
    assert response.status == 302
    assert response.headers["Location"] == "/"


async def test_callback_rejects_a_missing_or_wrong_state() -> None:
    app = make_auth_app(HTTPS)
    stub_discord(app, ALLOWED_UID)

    assert (await _callback(app, state=None)).status == 400
    assert (await _callback(app, cookie_state=None)).status == 400
    assert (await _callback(app, state="other")).status == 400
    # Discord must never have been contacted for any of those.
    http_of(app).post.assert_not_called()


async def test_callback_requires_a_code() -> None:
    app = make_auth_app(HTTPS)
    stub_discord(app, ALLOWED_UID)

    assert (await _callback(app, code=None)).status == 400
    http_of(app).post.assert_not_called()


async def test_callback_403s_a_non_allowlisted_user() -> None:
    app = make_auth_app(HTTPS)
    stub_discord(app, DENIED_UID)

    response = await _callback(app)
    assert response.status == 403
    assert auth.SESSION_COOKIE not in "\n".join(response.headers.getall("Set-Cookie", []))


@pytest.mark.parametrize(
    "failure",
    ["token", "me", "unreachable", "no_access_token", "no_id", "bad_id"],
)
async def test_callback_surfaces_discord_problems_as_502(failure: str) -> None:
    app = make_auth_app(HTTPS)

    if failure == "token":
        stub_token_failure(app)
    elif failure == "me":
        stub_me_failure(app)
    elif failure == "unreachable":
        stub_unreachable(app)
    elif failure == "no_access_token":
        http_of(app).post = MagicMock(return_value=FakeResponse(200, {"nope": 1}))
    elif failure == "no_id":
        http_of(app).post = MagicMock(return_value=FakeResponse(200, {"access_token": "at"}))
        http_of(app).get = MagicMock(return_value=FakeResponse(200, {"nope": 1}))
    else:
        http_of(app).post = MagicMock(return_value=FakeResponse(200, {"access_token": "at"}))
        http_of(app).get = MagicMock(return_value=FakeResponse(200, {"id": "not-a-number"}))

    response = await _callback(app)
    assert response.status == 502, failure
    assert auth.SESSION_COOKIE not in "\n".join(response.headers.getall("Set-Cookie", []))


async def test_callback_wraps_client_errors_as_502() -> None:
    app = make_auth_app(HTTPS)
    http_of(app).post = MagicMock(side_effect=aiohttp.ClientError("no route"))

    assert (await _callback(app)).status == 502


async def test_callback_503s_when_unconfigured() -> None:
    app = make_auth_app(UNCONFIGURED)
    assert (await _callback(app)).status == 503


# --- logout_handler ----------------------------------------------------------


async def test_logout_clears_the_session_and_returns_home() -> None:
    app = make_auth_app(HTTPS)
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/auth/logout", allow_redirects=False)

    assert response.status == 302
    assert response.headers["Location"] == "/"
    cleared = "\n".join(response.headers.getall("Set-Cookie", []))
    assert auth.SESSION_COOKIE in cleared


# --- end-to-end through both legs -------------------------------------------


async def test_full_login_journey_returns_a_working_session() -> None:
    """Walk login -> callback the way a browser would, sharing one cookie jar."""
    app = make_auth_app(HTTPS)
    stub_discord(app, ALLOWED_UID)

    async with TestClient(TestServer(app)) as client:
        login = await client.get("/auth/login?next=/gigs", allow_redirects=False)
        assert login.status == 302
        state = parse_qs(urlsplit(login.headers["Location"]).query)["state"][0]
        next_cookie = login.cookies.get(auth.NEXT_COOKIE)
        assert next_cookie is not None
        assert next_cookie.value == "/gigs"

        # Carry the cookies over explicitly. aiohttp's jar will not replay a Secure
        # cookie over the test server's plaintext http, and that policy is aiohttp's
        # rather than ours -- production is https, where the jar sends it fine.
        jar = "; ".join(f"{name}={morsel.value}" for name, morsel in login.cookies.items())
        assert auth.STATE_COOKIE in jar

        callback = await client.get(
            f"/auth/callback?state={state}&code=the-code",
            headers={"Cookie": jar},
            allow_redirects=False,
        )
        assert callback.status == 302
        assert callback.headers["Location"] == "/gigs"

        signed = callback.cookies[auth.SESSION_COOKIE].value

    request = make_mocked_request("GET", "/gigs", headers={"Cookie": f"{auth.SESSION_COOKIE}={signed}"})
    assert auth.verify_session(HTTPS, request) == ALLOWED_UID
