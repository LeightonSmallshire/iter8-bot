"""Shop browsing, credit leaderboard, and purchase API for the webapp."""

import datetime
import json
import os
from typing import Any

import discord
import logfire
from aiohttp import web

import utils.bot as bot_utils
import utils.database as db_utils
import utils.misc
import utils.shop as shop_utils
from utils.model import Purchase

from . import auth, keys


class ValidationError(Exception):
    """Bad user-supplied purchase input; message is safe to show the user."""


class LazyAnnouncer:
    """Announces via the configured shop channel; structurally satisfies bot_utils.Announcer."""

    def __init__(self, guild: discord.Guild) -> None:
        self._guild = guild

    def _channel(self) -> discord.TextChannel | None:
        raw = os.environ.get("SHOP_ANNOUNCE_CHANNEL_ID", "")
        if raw.isdigit():
            channel = self._guild.get_channel(int(raw))
            if isinstance(channel, discord.TextChannel):
                return channel
        return discord.utils.get(self._guild.text_channels, name="general-idiocy")

    async def send(
        self,
        content: str = "",
        *,
        embed: discord.Embed | None = None,
        allowed_mentions: discord.AllowedMentions | None = None,
        wait: bool = False,
    ) -> discord.Message:
        del wait
        channel = self._channel()
        if channel is None:
            raise shop_utils.ShopError("The announcement channel is unavailable.")
        kwargs: dict[str, Any] = {}
        if embed is not None:
            kwargs["embed"] = embed
        if allowed_mentions is not None:
            kwargs["allowed_mentions"] = allowed_mentions
        return await channel.send(content=content, **kwargs)


def compute_cost(item: type[shop_utils.ShopItem], params: dict[str, Any], sale: bool) -> int:
    """Mirror of the original Discord purchase cost math (view/shop_view.py)."""
    duration = params.get("duration")
    count = duration if duration else 1
    discount = 0.5 if sale else 1
    item_cost = item.COST * discount if item.ITEM_ID != shop_utils.BlackFridaySaleItem.ITEM_ID else item.COST
    return int(item_cost * count)


async def validate_params(
    item: type[shop_utils.ShopItem],
    raw: dict[str, Any],
    guild: discord.Guild,
    buyer_id: int,
) -> dict[str, Any]:
    """Port of the deleted Discord component guards into plain param validation."""
    out: dict[str, Any] = {}
    for field in item.WEB_FORM:
        value = raw.get(field.kind)
        if value is None or value == "":
            if field.required:
                raise ValidationError(f"{field.label} is required.")
            continue

        if field.kind == "user":
            if isinstance(value, bool) or not isinstance(value, int | str):
                raise ValidationError("Invalid selection.")
            if isinstance(value, str):
                if not value.isdigit():
                    raise ValidationError("Invalid selection.")
                value = int(value)
            try:
                member = await guild.fetch_member(value)
            except discord.NotFound:
                raise ValidationError("Invalid selection.") from None
            if member.bot or member.id == guild.owner_id or member.id == buyer_id:
                raise ValidationError("Invalid selection.")
            out["user"] = member.id
        elif field.kind == "duration":
            if isinstance(value, bool) or not isinstance(value, int) or value not in shop_utils.DURATION_CHOICES:
                raise ValidationError("Invalid duration.")
            out["duration"] = value
        elif field.kind == "text":
            if not isinstance(value, str):
                raise ValidationError(f"{field.label} is required.")
            limit = field.max_length or 500
            if len(value) > limit:
                raise ValidationError(f"{field.label} must be {limit} characters or fewer.")
            if field.required and not value.strip():
                raise ValidationError(f"{field.label} is required.")
            out["text"] = value
        elif field.kind == "colour":
            if not isinstance(value, str) or not shop_utils.COLOUR_RE.fullmatch(value.strip()):
                raise ValidationError("Invalid colour code. Use format like `#RRGGBB`.")
            out["colour"] = value.strip()
    return out


def _fmt(seconds: float) -> str:
    return utils.misc.format_timedelta(datetime.timedelta(seconds=round(seconds)))


def _item_groups(sale: bool) -> list[dict[str, Any]]:
    discount = 0.5 if sale else 1
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in shop_utils.SHOP_ITEMS:
        cost = item.COST * discount if item.ITEM_ID != shop_utils.BlackFridaySaleItem.ITEM_ID else item.COST
        cost = int(cost)
        grouped.setdefault(item.CATEGORY, []).append({
            "id": item.ITEM_ID,
            "name": item.DESCRIPTION,
            "cost": cost,
            "base_cost": item.COST,
            "auto_use": item.AUTO_USE,
            "price_display": _fmt(cost),
            "form": [
                {
                    "kind": f.kind,
                    "label": f.label,
                    "required": f.required,
                    "placeholder": f.placeholder,
                    "max_length": f.max_length,
                }
                for f in item.WEB_FORM
            ],
        })
    return [{"category": category, "items": items} for category, items in grouped.items()]


def _members(guild: discord.Guild, buyer_id: int) -> list[dict[str, Any]]:
    return [
        {"id": m.id, "name": m.display_name}
        for m in guild.members
        if not m.bot and m.id != guild.owner_id and m.id != buyer_id
    ]


def _get_guild(request: web.Request) -> discord.Guild | None:
    bot: discord.Client = request.app[keys.BOT_KEY]
    return bot.get_guild(bot_utils.Guilds.Default)


async def _payload(request: web.Request, uid: int) -> dict[str, Any] | None:
    guild = _get_guild(request)
    if guild is None:
        return None
    credits = await shop_utils.get_shop_credit(uid)
    sale, sale_end = await shop_utils.is_ongoing_sale()
    return {
        "uid": uid,
        "credits": credits,
        "credits_display": _fmt(credits),
        "sale": {"active": sale, "ends": sale_end.isoformat() if sale_end else None},
        "groups": _item_groups(sale),
        "members": _members(guild, uid),
        "durations": list(shop_utils.DURATION_CHOICES),
    }


async def shop_page(request: web.Request) -> web.StreamResponse:
    uid = auth.get_uid(request)
    payload = await _payload(request, uid)
    if payload is None:
        return web.Response(text=_SHOP_HTML.replace("__DATA__", "null"), status=503, content_type="text/html")
    data = json.dumps(payload).replace("<", "\\u003c")
    return web.Response(text=_SHOP_HTML.replace("__DATA__", data), content_type="text/html")


async def credits_page(request: web.Request) -> web.StreamResponse:
    uid = auth.get_uid(request)
    guild = _get_guild(request)
    if guild is None:
        return web.Response(text=_CREDITS_HTML.replace("__ROWS__", ""), status=503, content_type="text/html")

    rows: list[tuple[int, str, float]] = [
        (m.id, m.display_name, await shop_utils.get_shop_credit(m.id))
        for m in guild.members
        if not m.bot and m.id != guild.owner_id
    ]
    rows.sort(key=lambda row: row[2], reverse=True)

    body_rows = []
    for member_id, name, credit in rows:
        highlight = ' class="you"' if member_id == uid else ""
        body_rows.append(
            f"<tr{highlight}><td>{_esc(name)}</td><td>{_esc(_fmt(credit))}</td></tr>"
        )
    html = _CREDITS_HTML.replace("__ROWS__", "\n".join(body_rows))
    return web.Response(text=html, content_type="text/html")


async def api_shop(request: web.Request) -> web.StreamResponse:
    uid = auth.get_uid(request)
    payload = await _payload(request, uid)
    if payload is None:
        return web.json_response({"error": "Server unavailable."}, status=503)
    return web.json_response(payload)


async def api_credits(request: web.Request) -> web.StreamResponse:
    uid = auth.get_uid(request)
    guild = _get_guild(request)
    if guild is None:
        return web.json_response({"error": "Server unavailable."}, status=503)
    rows: list[dict[str, Any]] = []
    for m in guild.members:
        if m.bot or m.id == guild.owner_id:
            continue
        credit = await shop_utils.get_shop_credit(m.id)
        rows.append({"id": m.id, "name": m.display_name, "credit": credit, "display": _fmt(credit)})
    rows.sort(key=lambda row: row["credit"], reverse=True)
    return web.json_response({"you": uid, "rows": rows})


async def purchase_handler(request: web.Request) -> web.StreamResponse:
    uid = auth.get_uid(request)

    try:
        body: object = await request.json()
    except ValueError:
        return web.json_response({"error": "Invalid JSON."}, status=400)
    if not isinstance(body, dict):
        return web.json_response({"error": "Invalid request."}, status=400)

    item_id = body.get("item_id")
    raw_params = body.get("params", {})
    if isinstance(item_id, bool) or not isinstance(item_id, int):
        return web.json_response({"error": "Invalid item."}, status=400)
    if not isinstance(raw_params, dict):
        return web.json_response({"error": "Invalid request."}, status=400)

    item = next((i for i in shop_utils.SHOP_ITEMS if item_id == i.ITEM_ID), None)
    if item is None:
        return web.json_response({"error": "Unknown item."}, status=400)

    guild = _get_guild(request)
    if guild is None:
        return web.json_response({"error": "Server unavailable."}, status=503)
    try:
        buyer = await guild.fetch_member(uid)
    except discord.NotFound:
        return web.json_response({"error": "You are not a member of the server."}, status=403)

    try:
        params = await validate_params(item, raw_params, guild, uid)
    except ValidationError as exc:
        return web.json_response({"error": str(exc)}, status=400)

    sale, _ = await shop_utils.is_ongoing_sale()
    cost = compute_cost(item, params, sale)

    if not await shop_utils.can_afford_purchase(uid, cost):
        return web.json_response({"error": "You can't afford this purchase."}, status=403)

    ctx = shop_utils.ShopContext(guild=guild, buyer=buyer, announce=LazyAnnouncer(guild))

    db = await db_utils.Database(db_utils.DATABASE_NAME, defer_commit=True).connect()
    try:
        await db.insert(Purchase(timestamp=datetime.datetime.now(), item_id=item.ITEM_ID, cost=cost, user_id=uid, used=item.AUTO_USE))
        await item.handle_purchase(ctx, params)
        await db.commit()
    except BaseException as exc:
        await db.rollback()
        if not isinstance(exc, Exception):
            raise
        if isinstance(exc, shop_utils.ShopError):
            logfire.info(f"Shop purchase rejected: {exc}")
            return web.json_response({"error": str(exc)}, status=400)
        logfire.exception(f"Shop purchase failed: {item.DESCRIPTION}")
        return web.json_response({"error": f"Purchase failed to process ({exc})"}, status=500)

    credit = await shop_utils.get_shop_credit(uid)
    return web.json_response({"ok": True, "cost": cost, "credits": credit, "credits_display": _fmt(credit)})


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def register(app: web.Application) -> None:
    app.router.add_get("/shop", shop_page)
    app.router.add_get("/credits", credits_page)
    app.router.add_get("/api/shop", api_shop)
    app.router.add_get("/api/credits", api_credits)
    app.router.add_post("/api/shop/purchase", purchase_handler)


_NAV = """<header><nav>
<a href="/shop" class="active">🛒 Shop</a>
<a href="/credits">💵 Credits</a>
<a href="/gigs">🎟️ Gigs</a>
<a href="/">Home</a>
<a href="/auth/logout" class="right">Log out</a>
</nav></header>"""

_SHOP_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Timeout Shop</title>
<link rel="stylesheet" href="/static/shop.css">
</head>
<body>
{_NAV}
<main>
<div class="banner" id="sale-banner" hidden></div>
<div class="balance">Your credit: <b id="credits"></b></div>
<div id="grid"></div>
</main>
<div id="backdrop" class="hidden" role="dialog" aria-modal="true">
<div id="modal">
<h2 id="modal-title"></h2>
<p id="modal-price"></p>
<form id="buy-form"></form>
<p id="modal-error" class="error" hidden></p>
<div class="actions">
<button type="button" id="cancel-btn">Cancel</button>
<button type="button" id="confirm-btn" class="primary">Confirm Purchase</button>
</div>
</div>
</div>
<div id="toast" class="hidden"></div>
<script>window.SHOP = __DATA__;</script>
<script src="/static/shop.js"></script>
</body>
</html>"""

_CREDITS_HTML = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Credits</title>
<link rel="stylesheet" href="/static/shop.css">
</head>
<body>
{_NAV}
<main>
<h1>💵 How much is everyone worth?</h1>
<table class="credits">
<thead><tr><th>Member</th><th>Credit</th></tr></thead>
<tbody>
__ROWS__
</tbody>
</table>
</main>
</body>
</html>"""
