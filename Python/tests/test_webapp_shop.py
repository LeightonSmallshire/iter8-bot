"""Tests for webapp.shop: cost math, param validation, and purchase rollback on ShopError."""

import types
from typing import Any, cast

import discord
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import utils.database as db_utils
import utils.shop as shop_utils
import webapp.shop as shop_module
from utils import allowlist
from utils.model import Purchase
from webapp import auth, keys
from webapp.shop import ValidationError, compute_cost, validate_params

ALLOWED_UID = next(iter(allowlist.ALLOWED_IDS))
CONFIG = auth.AuthConfig(
    client_id="cid",
    client_secret="secret",
    base_url="http://test.local",
    session_secret="session-secret",
)


def _not_found() -> discord.NotFound:
    response = types.SimpleNamespace(status=404, reason="Not Found")
    return discord.NotFound(cast(Any, response), "Unknown User")


class FakeMember:
    def __init__(self, member_id: int, bot: bool = False) -> None:
        self.id = member_id
        self.bot = bot


class FakeGuild:
    def __init__(self, members: list[FakeMember], owner_id: int = 999) -> None:
        self.owner_id = owner_id
        self.members = [cast(Any, m) for m in members]
        self._by_id = {m.id: m for m in members}

    async def fetch_member(self, member_id: int) -> FakeMember:
        member = self._by_id.get(member_id)
        if member is None:
            raise _not_found()
        return member


def _guild() -> discord.Guild:
    return cast(discord.Guild, FakeGuild([FakeMember(555), FakeMember(666, bot=True)], owner_id=999))


# --- compute_cost -----------------------------------------------------------------


def test_cost_without_duration_counts_one() -> None:
    assert compute_cost(shop_utils.BullyTimeoutItem, {}, sale=False) == 30
    assert compute_cost(shop_utils.ChooseColourOwnItem, {"colour": "#ff0000"}, sale=False) == 60


def test_cost_multiplies_by_duration() -> None:
    assert compute_cost(shop_utils.BullyTimeoutItem, {"duration": 5}, sale=False) == 150
    assert compute_cost(shop_utils.BullyTimeoutItem, {"duration": 60}, sale=False) == 1800


def test_cost_half_off_during_sale() -> None:
    assert compute_cost(shop_utils.BullyTimeoutItem, {"duration": 5}, sale=True) == 75
    assert compute_cost(shop_utils.BullyTimeoutItem, {}, sale=True) == 15


def test_black_friday_item_never_discounted() -> None:
    assert compute_cost(shop_utils.BlackFridaySaleItem, {}, sale=True) == 1800
    assert compute_cost(shop_utils.BlackFridaySaleItem, {}, sale=False) == 1800


# --- validate_params --------------------------------------------------------------


async def test_duration_validation() -> None:
    guild = _guild()
    with pytest.raises(ValidationError, match="Duration is required"):
        await validate_params(shop_utils.BullyTimeoutItem, {}, guild, 42)
    for bad in (7, True, "5", 0.5):
        with pytest.raises(ValidationError, match="Invalid duration"):
            await validate_params(shop_utils.BullyTimeoutItem, {"duration": bad}, guild, 42)
    assert await validate_params(shop_utils.BullyTimeoutItem, {"duration": 5}, guild, 42) == {"duration": 5}


async def test_optional_reason_accepted_and_omitted() -> None:
    guild = _guild()
    assert await validate_params(shop_utils.BullyTimeoutItem, {"duration": 1}, guild, 42) == {"duration": 1}
    out = await validate_params(shop_utils.BullyTimeoutItem, {"duration": 1, "text": "why not"}, guild, 42)
    assert out == {"duration": 1, "text": "why not"}
    with pytest.raises(ValidationError, match="Reason must be 500 characters or fewer"):
        await validate_params(shop_utils.BullyTimeoutItem, {"duration": 1, "text": "x" * 501}, guild, 42)


async def test_nickname_text_validation() -> None:
    guild = _guild()
    with pytest.raises(ValidationError, match="Nickname is required"):
        await validate_params(shop_utils.ChooseNicknameOwnItem, {"text": "   "}, guild, 42)
    with pytest.raises(ValidationError, match="Nickname is required"):
        await validate_params(shop_utils.ChooseNicknameOwnItem, {"text": 42}, guild, 42)
    with pytest.raises(ValidationError, match="Nickname must be 32 characters or fewer"):
        await validate_params(shop_utils.ChooseNicknameOwnItem, {"text": "x" * 33}, guild, 42)
    out = await validate_params(shop_utils.ChooseNicknameOwnItem, {"text": "Botty"}, guild, 42)
    assert out == {"text": "Botty"}


async def test_user_validation() -> None:
    guild = _guild()
    assert await validate_params(shop_utils.BullyChooseItem, {"user": 555}, guild, 42) == {"user": 555}
    assert await validate_params(shop_utils.BullyChooseItem, {"user": "555"}, guild, 42) == {"user": 555}
    for bad in (666, 999, 42, 777, True, "abc", 12.5, [555]):
        with pytest.raises(ValidationError, match="Invalid selection"):
            await validate_params(shop_utils.BullyChooseItem, {"user": bad}, guild, 42)
    with pytest.raises(ValidationError, match="Target is required"):
        await validate_params(shop_utils.BullyChooseItem, {}, guild, 42)


async def test_colour_validation() -> None:
    guild = _guild()
    assert await validate_params(shop_utils.ChooseColourOwnItem, {"colour": "#ff8800"}, guild, 42) == {
        "colour": "#ff8800",
    }
    assert await validate_params(shop_utils.ChooseColourOwnItem, {"colour": "#FFF"}, guild, 42) == {
        "colour": "#FFF",
    }
    for bad in ("ff8800", "#GGGGGG", "red", 42):
        with pytest.raises(ValidationError, match="Invalid colour code"):
            await validate_params(shop_utils.ChooseColourOwnItem, {"colour": bad}, guild, 42)
    with pytest.raises(ValidationError, match="Colour is required"):
        await validate_params(shop_utils.ChooseColourOwnItem, {}, guild, 42)


# --- purchase handler -------------------------------------------------------------


class FakeDB:
    def __init__(self) -> None:
        self.inserted: list[Purchase] = []
        self.committed = False
        self.rolled_back = False

    async def insert(self, row: Purchase) -> None:
        self.inserted.append(row)

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True


class FakeBot:
    def __init__(self, guild: FakeGuild | None) -> None:
        self._guild = guild

    def get_guild(self, guild_id: int) -> FakeGuild | None:
        del guild_id
        return self._guild


class FakeDatabase:
    db: FakeDB | None = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    async def connect(self) -> FakeDB:
        assert FakeDatabase.db is not None
        return FakeDatabase.db


def _const(value: Any) -> Any:
    async def call(*args: Any, **kwargs: Any) -> Any:
        del args, kwargs
        return value

    return call


def _purchase_app(
    monkeypatch: pytest.MonkeyPatch,
    fake_db: FakeDB | None,
    *,
    afford: bool = True,
    handle_fails: bool = False,
) -> web.Application:
    async def handle_ok(ctx: Any, params: Any) -> None:
        del ctx, params

    async def handle_fail(ctx: Any, params: Any) -> None:
        del ctx, params
        raise shop_utils.ShopError("No timeout farming")

    monkeypatch.setattr(shop_utils, "is_ongoing_sale", _const((False, None)))
    monkeypatch.setattr(shop_utils, "can_afford_purchase", _const(afford))
    monkeypatch.setattr(shop_utils, "get_shop_credit", _const(42.5))
    monkeypatch.setattr(
        shop_utils.BullyTimeoutItem,
        "handle_purchase",
        handle_fail if handle_fails else handle_ok,
    )
    if fake_db is not None:
        monkeypatch.setattr(FakeDatabase, "db", fake_db)
        monkeypatch.setattr(db_utils, "Database", FakeDatabase)

    guild = FakeGuild([FakeMember(ALLOWED_UID)])
    app = web.Application(middlewares=[auth.require_session])
    app[auth.AUTH_KEY] = CONFIG
    app[keys.BOT_KEY] = cast(discord.Client, FakeBot(guild))
    app.router.add_post("/api/shop/purchase", shop_module.purchase_handler)
    return app


async def _post(client: TestClient[web.Request, web.Application], body: dict[str, Any]) -> Any:
    cookie = f"{auth.SESSION_COOKIE}={auth.make_session_value(CONFIG, ALLOWED_UID)}"
    return await client.post("/api/shop/purchase", json=body, headers={"Cookie": cookie})


async def test_purchase_success_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = FakeDB()
    app = _purchase_app(monkeypatch, fake_db)
    async with TestClient(TestServer(app)) as client:
        response = await _post(client, {"item_id": 5, "params": {"duration": 5}})
        status = response.status
        data = await response.json()
    assert status == 200
    assert data["ok"] is True
    assert data["cost"] == 150
    assert data["credits"] == 42.5
    assert fake_db.committed and not fake_db.rolled_back
    assert len(fake_db.inserted) == 1
    purchase = fake_db.inserted[0]
    assert purchase.item_id == 5
    assert purchase.cost == 150
    assert purchase.user_id == ALLOWED_UID
    assert purchase.used is True


async def test_purchase_shop_error_rolls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_db = FakeDB()
    app = _purchase_app(monkeypatch, fake_db, handle_fails=True)
    async with TestClient(TestServer(app)) as client:
        response = await _post(client, {"item_id": 5, "params": {"duration": 5}})
        status = response.status
        body = await response.json()
    assert status == 400
    assert body["error"] == "No timeout farming"
    assert fake_db.rolled_back and not fake_db.committed
    assert len(fake_db.inserted) == 1


async def test_purchase_cannot_afford(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _purchase_app(monkeypatch, None, afford=False)
    async with TestClient(TestServer(app)) as client:
        response = await _post(client, {"item_id": 5, "params": {"duration": 5}})
        status = response.status
        body = await response.json()
    assert status == 403
    assert body["error"] == "You can't afford this purchase."


async def test_purchase_rejects_bad_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    app = _purchase_app(monkeypatch, None)
    async with TestClient(TestServer(app)) as client:
        response = await _post(client, {"item_id": 999})
        assert response.status == 400
        assert (await response.json())["error"] == "Unknown item."

        response = await _post(client, {"item_id": "5"})
        assert response.status == 400

        response = await _post(client, {"item_id": 5, "params": {"duration": 99}})
        assert response.status == 400
        assert (await response.json())["error"] == "Invalid duration."

        cookie = f"{auth.SESSION_COOKIE}={auth.make_session_value(CONFIG, ALLOWED_UID)}"
        response = await client.post(
            "/api/shop/purchase",
            data="not json",
            headers={"Cookie": cookie, "Content-Type": "application/json"},
        )
        assert response.status == 400
        assert (await response.json())["error"] == "Invalid JSON."
