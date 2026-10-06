"""Tests for webapp.auth session cookies and the require_session middleware."""

import base64
import hashlib
import hmac

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request

from utils import allowlist
from webapp import auth

ALLOWED_UID = next(iter(allowlist.ALLOWED_IDS))
DENIED_UID = next(uid for uid in range(1, 10_000_000) if not allowlist.is_allowed(uid))
CONFIG = auth.AuthConfig(
    client_id="cid",
    client_secret="secret",
    base_url="http://test.local",
    session_secret="session-secret",
)


def _raw_request(value: str | None) -> web.Request:
    headers = {"Cookie": f"{auth.SESSION_COOKIE}={value}"} if value is not None else {}
    return make_mocked_request("GET", "/shop", headers=headers)


def _expired_session_value(user_id: int) -> str:
    expiry = 1  # far in the past
    message = f"{user_id}.{expiry}".encode("ascii")
    signature = base64.urlsafe_b64encode(
        hmac.new(CONFIG.session_secret.encode("utf-8"), message, hashlib.sha256).digest(),
    ).rstrip(b"=").decode("ascii")
    return f"{user_id}.{expiry}.{signature}"


def test_session_round_trip() -> None:
    value = auth.make_session_value(CONFIG, ALLOWED_UID)
    assert auth.verify_session(CONFIG, _raw_request(value)) == ALLOWED_UID


def test_missing_or_malformed_cookie() -> None:
    for value in (None, "", "abc", "1.2", "a.b.c", "1.x.abc", "1.2.3.4"):
        assert auth.verify_session(CONFIG, _raw_request(value)) is None


def test_tampered_signature_rejected() -> None:
    value = auth.make_session_value(CONFIG, ALLOWED_UID)
    tampered = value[:-3] + ("aaa" if not value.endswith("aaa") else "bbb")
    assert auth.verify_session(CONFIG, _raw_request(tampered)) is None


def test_expired_session_rejected() -> None:
    assert auth.verify_session(CONFIG, _raw_request(_expired_session_value(ALLOWED_UID))) is None


def test_non_allowlisted_user_rejected() -> None:
    value = auth.make_session_value(CONFIG, DENIED_UID)
    assert auth.verify_session(CONFIG, _raw_request(value)) is None


def test_unconfigured_auth_rejects_everything() -> None:
    unconfigured = auth.AuthConfig(client_id="", client_secret="", base_url="", session_secret="")
    value = auth.make_session_value(CONFIG, ALLOWED_UID)
    assert auth.verify_session(unconfigured, _raw_request(value)) is None


def test_safe_next() -> None:
    assert auth._safe_next("/shop")
    assert auth._safe_next("/shop?tab=a")
    assert not auth._safe_next("//evil.example")
    assert not auth._safe_next("https://evil.example")
    assert not auth._safe_next("/shop\\..\\evil")


def _app() -> web.Application:
    app = web.Application(middlewares=[auth.require_session])
    app[auth.AUTH_KEY] = CONFIG

    async def landing(request: web.Request) -> web.StreamResponse:
        del request
        return web.Response(text="ok")

    async def echo(request: web.Request) -> web.StreamResponse:
        return web.json_response({"uid": auth.get_uid(request)})

    app.router.add_get("/", landing)
    app.router.add_get("/healthz", landing)
    app.router.add_get("/static/style.css", landing)
    app.router.add_get("/legacy/index.html", landing)
    app.router.add_get("/go.html", landing)
    app.router.add_get("/tictactoe.html", landing)
    app.router.add_get("/shop", echo)
    app.router.add_get("/api/credits", echo)
    return app


async def test_middleware_gating() -> None:
    async with TestClient(TestServer(_app())) as client:
        for path in ("/", "/healthz", "/static/style.css", "/legacy/index.html", "/go.html", "/tictactoe.html"):
            response = await client.get(path)
            assert response.status == 200, path

        response = await client.get("/api/credits")
        assert response.status == 401
        assert (await response.json())["error"] == "Not logged in."

        response = await client.get("/shop", allow_redirects=False)
        assert response.status == 302
        assert response.headers["Location"] == "/auth/login?next=/shop"

        response = await client.get("/shop?tab=a", allow_redirects=False)
        assert response.status == 302
        assert response.headers["Location"] == "/auth/login?next=/shop?tab%3Da"

        cookie = f"{auth.SESSION_COOKIE}={auth.make_session_value(CONFIG, ALLOWED_UID)}"
        response = await client.get("/shop", headers={"Cookie": cookie})
        assert response.status == 200
        assert (await response.json())["uid"] == ALLOWED_UID

        denied = f"{auth.SESSION_COOKIE}={auth.make_session_value(CONFIG, DENIED_UID)}"
        response = await client.get("/api/credits", headers={"Cookie": denied})
        assert response.status == 401
        response = await client.get("/shop", headers={"Cookie": denied}, allow_redirects=False)
        assert response.status == 302
