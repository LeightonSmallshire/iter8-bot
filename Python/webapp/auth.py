"""Discord OAuth2 login and HMAC-signed session cookies for the webapp."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import aiohttp
from aiohttp import web

import utils.allowlist as allowlist

from .keys import HTTP_KEY

DISCORD_AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_ME_URL = "https://discord.com/api/users/@me"

SESSION_COOKIE = "iter8_session"
STATE_COOKIE = "iter8_state"
NEXT_COOKIE = "iter8_next"

SESSION_TTL_SECONDS = 7 * 24 * 3600
STATE_TTL_SECONDS = 600

OPEN_PATHS = frozenset({
    "/",
    "/healthz",
    "/auth/login",
    "/auth/callback",
    "/auth/logout",
    # Discord's frame calls this before it holds any session, so it has to be open.
    # Safe for the same reason /auth/callback is: the code is only ever issued to the
    # signed-in user by the Embedded App SDK, and Discord validates it here.
    "/auth/exchange",
    "/go.html",
    "/tictactoe.html",
})

# Prefixes served without a session: our own assets plus the legacy static pages.
OPEN_PREFIXES = ("/static/", "/legacy/")

MiddlewareHandler = Callable[[web.Request], Awaitable[web.StreamResponse]]


@dataclass(frozen=True)
class AuthConfig:
    client_id: str
    client_secret: str
    base_url: str
    session_secret: str
    activity_url: str = ""

    @classmethod
    def from_env(cls) -> "AuthConfig":
        return cls(
            client_id=os.environ.get("DISCORD_CLIENT_ID", ""),
            client_secret=os.environ.get("DISCORD_CLIENT_SECRET", ""),
            base_url=os.environ.get("WEBAPP_BASE_URL", ""),
            session_secret=os.environ.get("WEBAPP_SESSION_SECRET", ""),
            activity_url=os.environ.get("WEBAPP_ACTIVITY_URL", ""),
        )

    @property
    def configured(self) -> bool:
        return not self.missing_fields

    @property
    def missing_fields(self) -> list[str]:
        values = {
            "DISCORD_CLIENT_ID": self.client_id,
            "DISCORD_CLIENT_SECRET": self.client_secret,
            "WEBAPP_BASE_URL": self.base_url,
            "WEBAPP_SESSION_SECRET": self.session_secret,
        }
        return [name for name, value in values.items() if not value]

    @property
    def redirect_uri(self) -> str:
        return self.base_url.rstrip("/") + "/auth/callback"

    @property
    def secure_cookies(self) -> bool:
        return self.base_url.startswith("https://")

    @property
    def same_site(self) -> str:
        """Cookie SameSite attribute.

        Discord proxies the Activity through ``<application id>.discordsays.com`` and
        frames it inside ``discord.com``, which makes requests to our origin cross-site,
        so the session cookie has to be ``SameSite=None`` to be sent at all. Browsers
        reject ``SameSite=None`` without ``Secure``, so only use it over https and keep
        ``Lax`` for plain-http local development.
        """
        return "None" if self.secure_cookies else "Lax"

    @property
    def activity_redirect_uri(self) -> str:
        """The URL registered as the Activity URL in the Discord developer portal.

        Discord serves the Activity through its own origin but requires the token
        exchange to present the registered URL as ``redirect_uri``, so it must match
        exactly. Defaults to the public origin.
        """
        return (self.activity_url or self.base_url).rstrip("/")


AUTH_KEY: web.AppKey[AuthConfig] = web.AppKey("auth", AuthConfig)
UID_KEY: web.RequestKey[int] = web.RequestKey("uid", int)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sign(secret: str, message: bytes) -> str:
    return _b64(hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest())


def make_session_value(auth: AuthConfig, user_id: int) -> str:
    expires = int(time.time()) + SESSION_TTL_SECONDS
    message = f"{user_id}.{expires}".encode("ascii")
    return f"{user_id}.{expires}.{_sign(auth.session_secret, message)}"


def verify_session(auth: AuthConfig, request: web.Request) -> int | None:
    """Return the allowlisted user id carried by a valid session cookie, else None."""
    if not auth.configured:
        return None
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    user_part, expiry_part, signature = parts
    if not (user_part.isdigit() and expiry_part.isdigit()):
        return None
    message = f"{user_part}.{expiry_part}".encode("ascii")
    if not hmac.compare_digest(signature, _sign(auth.session_secret, message)):
        return None
    if int(expiry_part) < time.time():
        return None
    user_id = int(user_part)
    if not allowlist.is_allowed(user_id):
        return None
    return user_id


def get_uid(request: web.Request) -> int:
    """User id stamped on the request by the require_session middleware."""
    uid = request.get(UID_KEY)
    assert isinstance(uid, int)
    return uid


def _safe_next(value: str) -> bool:
    return value.startswith("/") and not value.startswith("//") and "\\" not in value


async def login_handler(request: web.Request) -> web.StreamResponse:
    auth: AuthConfig = request.app[AUTH_KEY]
    if not auth.configured:
        raise web.HTTPServiceUnavailable(text="Login is not configured yet.")

    next_path = request.query.get("next", "/")
    if not _safe_next(next_path):
        next_path = "/"

    state = secrets.token_urlsafe(32)
    query = urlencode({
        "client_id": auth.client_id,
        "redirect_uri": auth.redirect_uri,
        "response_type": "code",
        "scope": "identify",
        "state": state,
    })

    response = web.HTTPFound(f"{DISCORD_AUTHORIZE_URL}?{query}")
    response.set_cookie(
        STATE_COOKIE, state, max_age=STATE_TTL_SECONDS, httponly=True, samesite=auth.same_site,
        secure=auth.secure_cookies, path="/",
    )
    response.set_cookie(
        NEXT_COOKIE, next_path, max_age=STATE_TTL_SECONDS, httponly=True, samesite=auth.same_site,
        secure=auth.secure_cookies, path="/",
    )
    raise response


async def _discord_user_id(auth: AuthConfig, http: aiohttp.ClientSession, code: str, redirect_uri: str) -> int:
    """Trade an OAuth authorization code for the Discord user id behind it.

    Shared by the classic redirect callback and the Discord Activity exchange, which
    differ only in the ``redirect_uri`` they present.
    """

    try:
        async with http.post(
            DISCORD_TOKEN_URL,
            data={
                "client_id": auth.client_id,
                "client_secret": auth.client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        ) as token_response:
            token_data: object = await token_response.json(content_type=None)
        if (
            token_response.status != 200
            or not isinstance(token_data, dict)
            or "access_token" not in token_data
        ):
            raise web.HTTPBadGateway(text="Discord token exchange failed.")

        async with http.get(
            DISCORD_ME_URL,
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        ) as me_response:
            user_data: object = await me_response.json(content_type=None)
        if me_response.status != 200 or not isinstance(user_data, dict):
            raise web.HTTPBadGateway(text="Discord user fetch failed.")
    except aiohttp.ClientError as exc:
        raise web.HTTPBadGateway(text="Could not reach Discord.") from exc

    try:
        return int(user_data["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise web.HTTPBadGateway(text="Unexpected Discord user payload.") from exc


async def callback_handler(request: web.Request) -> web.StreamResponse:
    auth: AuthConfig = request.app[AUTH_KEY]
    if not auth.configured:
        raise web.HTTPServiceUnavailable(text="Login is not configured yet.")

    state = request.query.get("state", "")
    expected_state = request.cookies.get(STATE_COOKIE, "")
    if not state or not expected_state or not hmac.compare_digest(state, expected_state):
        raise web.HTTPBadRequest(text="Invalid OAuth state.")

    code = request.query.get("code")
    if not code:
        raise web.HTTPBadRequest(text="Missing authorization code.")

    http: aiohttp.ClientSession = request.app[HTTP_KEY]

    user_id = await _discord_user_id(auth, http, code, auth.redirect_uri)

    if not allowlist.is_allowed(user_id):
        raise web.HTTPForbidden(text="You're not on the list. Ask a Paradise member to add you.")

    next_path = request.cookies.get(NEXT_COOKIE, "/")
    if not _safe_next(next_path):
        next_path = "/"

    response = web.HTTPFound(next_path)
    response.set_cookie(
        SESSION_COOKIE, make_session_value(auth, user_id), max_age=SESSION_TTL_SECONDS,
        httponly=True, samesite=auth.same_site, secure=auth.secure_cookies, path="/",
    )
    response.del_cookie(STATE_COOKIE, path="/")
    response.del_cookie(NEXT_COOKIE, path="/")
    raise response


async def exchange_handler(request: web.Request) -> web.StreamResponse:
    """Complete a Discord Activity sign-in.

    Discord frames the Activity through ``<application id>.discordsays.com`` and refuses
    to have its own authorize page framed, so the classic redirect cannot work in there.
    Instead the embedded SDK runs inside the iframe and hands us an authorization code,
    which we exchange here. Because this request originates inside the iframe, the
    ``Set-Cookie`` below is attributed to Discord's proxy host rather than our domain,
    which is what makes the session usable for subsequent in-frame requests.
    """
    auth: AuthConfig = request.app[AUTH_KEY]
    if not auth.configured:
        raise web.HTTPServiceUnavailable(text="Login is not configured yet.")

    try:
        payload: object = await request.json()
    except (json.JSONDecodeError, ValueError) as exc:
        raise web.HTTPBadRequest(text="Expected a JSON body.") from exc
    if not isinstance(payload, dict):
        raise web.HTTPBadRequest(text="Expected a JSON body.")

    code = payload.get("code")
    if not isinstance(code, str) or not code.strip():
        raise web.HTTPBadRequest(text="Missing authorization code.")

    http: aiohttp.ClientSession = request.app[HTTP_KEY]
    user_id = await _discord_user_id(auth, http, code.strip(), auth.activity_redirect_uri)

    if not allowlist.is_allowed(user_id):
        raise web.HTTPForbidden(text="You're not on the list. Ask a Paradise member to add you.")

    response = web.json_response({"ok": True})
    response.set_cookie(
        SESSION_COOKIE, make_session_value(auth, user_id), max_age=SESSION_TTL_SECONDS,
        httponly=True, samesite=auth.same_site, secure=auth.secure_cookies, path="/",
    )
    return response


async def logout_handler(request: web.Request) -> web.StreamResponse:
    response = web.HTTPFound("/")
    response.del_cookie(SESSION_COOKIE, path="/")
    raise response


@web.middleware
async def require_session(request: web.Request, handler: MiddlewareHandler) -> web.StreamResponse:
    path = request.path
    if path in OPEN_PATHS or path.startswith(OPEN_PREFIXES):
        return await handler(request)

    auth: AuthConfig = request.app[AUTH_KEY]
    user_id = verify_session(auth, request)
    if user_id is None:
        if path.startswith("/api/"):
            return web.json_response({"error": "Not logged in."}, status=401)
        target = path + ("?" + request.query_string if request.query_string else "")
        raise web.HTTPFound("/auth/login?next=" + quote(target, safe="/"))

    request[UID_KEY] = user_id
    return await handler(request)
