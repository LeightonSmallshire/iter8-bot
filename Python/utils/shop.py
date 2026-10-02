import datetime
import re
import secrets
from dataclasses import dataclass
from typing import Any, Literal, cast

import discord
import discord.utils

from .bot import Announcer, Roles, do_role_roll, get_non_bot_users, on_new_admin
from .database import DATABASE_NAME, Database, OrderParam, WhereParam
from .model import AdminBet, GambleWin, Gift, Purchase, User

SHOP_ITEMS = list[type['ShopItem']]()

DURATION_CHOICES: tuple[int, ...] = (1, 2, 5, 10, 15, 30, 60)
COLOUR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}){1,2}$")

FormFieldKind = Literal["user", "duration", "text", "colour"]


@dataclass(frozen=True)
class FormField:
    kind: FormFieldKind
    label: str
    required: bool = True
    placeholder: str = ""
    max_length: int | None = None


class ShopError(Exception):
    """Raised by handle_purchase to abort a purchase with a human-readable message (rolls back)."""


@dataclass
class ShopContext:
    guild: discord.Guild
    buyer: discord.Member
    announce: Announcer


class ShopItem:
    ITEM_ID: int
    COST: int
    DESCRIPTION: str
    AUTO_USE: bool
    CATEGORY: str
    WEB_FORM: tuple[FormField, ...] = ()

    def __init_subclass__(cls) -> None:
        assert hasattr(cls, 'ITEM_ID') and isinstance(cls.ITEM_ID, int)
        assert hasattr(cls, 'COST') and isinstance(cls.COST, int)
        assert hasattr(cls, 'DESCRIPTION') and isinstance(cls.DESCRIPTION, str)
        assert hasattr(cls, 'AUTO_USE') and isinstance(cls.AUTO_USE, bool)
        assert hasattr(cls, 'CATEGORY') and isinstance(cls.CATEGORY, str)
        assert isinstance(cls.WEB_FORM, tuple)

        SHOP_ITEMS.append(cls)

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        target = await ctx.guild.fetch_member(params['user'])

        if target.id == ctx.buyer.id:
            raise ShopError('No timeout farming')

        now = discord.utils.utcnow()
        start = max(now, target.timed_out_until) if target.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text")

        await target.timeout(until, reason=f"<@{ctx.buyer.id}> used the power of the shop{f' for {reason}' if reason else ''}.")


class BullyTimeoutItem(ShopItem):
    ITEM_ID = 5
    COST = 30
    DESCRIPTION = "⏱️ Timeout bully target (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"
    WEB_FORM = (
        FormField("duration", "Duration"),
        FormField("text", "Reason", required=False, placeholder="Enter reason..."),
    )

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        role = await ctx.guild.fetch_role(Roles.BullyTarget)
        member = role.members[0]

        if member.id == ctx.buyer.id:
            raise ShopError('No timeout farming')

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text")

        await member.timeout(until, reason=f"<@{ctx.buyer.id}> decided to bully the prey of the dice{f' for {reason}' if reason else ''}.")


class TimeoutRandomItem(ShopItem):
    ITEM_ID = 14
    COST = 30
    DESCRIPTION = "⏱️ Timeout a random target (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"
    WEB_FORM = (
        FormField("duration", "Duration"),
        FormField("text", "Reason", required=False, placeholder="Enter reason..."),
    )

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        users = get_non_bot_users(ctx.guild)

        index = secrets.randbelow(len(users))

        member = await ctx.guild.fetch_member(users[index])

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text")

        await member.timeout(until, reason=f"<@{ctx.buyer.id}> decided to bully someone at random{f' for {reason}' if reason else ''}.")


async def make_bully_reroll_table(ctx: ShopContext) -> list[int]:
    guild = ctx.guild
    admin_role = await guild.fetch_role(Roles.Admin)
    bully_role = await guild.fetch_role(Roles.BullyTarget)
    filter_users = [u.id for u in admin_role.members] + [u.id for u in bully_role.members if u.id != ctx.buyer.id]
    return [x for x in get_non_bot_users(guild) if x not in filter_users]


class BullyRerollItem(ShopItem):
    ITEM_ID = 3
    COST = 600
    DESCRIPTION = "🎲 Reroll bully target"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        await do_role_roll(
            ctx.guild,
            ctx.announce,
            Roles.BullyTarget,
            await make_bully_reroll_table(ctx),
            f"🎲 {ctx.buyer.display_name} is re-rolling the bully target!",
            ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!")
        )


class BullyChooseItem(ShopItem):
    ITEM_ID = 4
    COST = 1200
    DESCRIPTION = "🤕 Choose bully target"
    AUTO_USE = True
    CATEGORY = "Timeouts"
    WEB_FORM = (FormField("user", "Target"),)

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        guild = ctx.guild
        role = await guild.fetch_role(Roles.BullyTarget)
        new_target = await guild.fetch_member(params['user'])
        current_target = role.members[0]

        admin_role = await guild.fetch_role(Roles.Admin)
        if new_target in admin_role.members:
            raise ShopError("Can't make the admin the bully target.")

        await current_target.remove_roles(role)
        await new_target.add_roles(role)


class AdminTicketItem(ShopItem):
    ITEM_ID = 7
    COST = 1800
    DESCRIPTION = "🎟️ Add an extra ticket in the next admin dice roll"
    AUTO_USE = False
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        pass


class AdminRerollItem(ShopItem):
    ITEM_ID = 8
    COST = 2700
    DESCRIPTION = "🎲 Reroll the admin"
    AUTO_USE = True
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        guild = ctx.guild
        roll_table = get_non_bot_users(guild)

        bully_role = await guild.fetch_role(Roles.BullyTarget)
        bully_targets = [u.id for u in bully_role.members]

        new_admin = await do_role_roll(
            guild,
            ctx.announce,
            Roles.Admin,
            roll_table,
            f"🚨 {ctx.buyer.display_name} called for a reroll! 🚨",
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>.")
        )
        await on_new_admin(guild, new_admin)

        if new_admin in bully_targets:
            await do_role_roll(
                guild,
                ctx.announce,
                Roles.BullyTarget,
                await make_bully_reroll_table(ctx),
                "🎲 Admin landed on the bully target. Finding a new target...",
                ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!")
            )


class MakeAdminItem(ShopItem):
    ITEM_ID = 6
    COST = 7200
    DESCRIPTION = "👑 Make yourself admin"
    AUTO_USE = True
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        guild = ctx.guild
        role = await guild.fetch_role(Roles.Admin)
        new_target = await guild.fetch_member(ctx.buyer.id)

        for member in role.members:
            await member.remove_roles(role)

        await new_target.add_roles(role)
        await on_new_admin(guild, new_target.id)

        await ctx.announce.send(content=f"@everyone {ctx.buyer.mention} just made themselves an Admin!", allowed_mentions=discord.AllowedMentions(roles=True))

        bully_role = await guild.fetch_role(Roles.BullyTarget)
        bully_targets = [u.id for u in bully_role.members]

        if ctx.buyer.id in bully_targets:
            await do_role_roll(
                guild,
                ctx.announce,
                Roles.BullyTarget,
                await make_bully_reroll_table(ctx),
                "🎲 Admin landed on the bully target. Finding a new target...",
                ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!")
            )


class ChooseNicknameOwnItem(ShopItem):
    ITEM_ID = 9
    COST = 60
    DESCRIPTION = "✏️ Change your own nickname"
    AUTO_USE = True
    CATEGORY = "Customise"
    WEB_FORM = (
        FormField("text", "Nickname", placeholder="Enter a nickname...", max_length=32),
    )

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        new_nick = params['text']
        member = await ctx.guild.fetch_member(ctx.buyer.id)
        await member.edit(nick=new_nick)


class ChooseNicknameOtherItem(ShopItem):
    ITEM_ID = 10
    COST = 300
    DESCRIPTION = "✏️ Change another user's nickname"
    AUTO_USE = True
    CATEGORY = "Customise"
    WEB_FORM = (
        FormField("user", "Target"),
        FormField("text", "Nickname", placeholder="Enter a nickname...", max_length=32),
    )

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        new_nick = params['text']
        target = await ctx.guild.fetch_member(params['user'])
        await target.edit(nick=new_nick)


def colour_from_hex(code: str) -> discord.Color:
    code = code.lstrip('#')
    if len(code) == 3:
        code = ''.join(ch*2 for ch in code)
    return discord.Color(int(code, 16))


async def set_colour(guild: discord.Guild, target: discord.Member, params: dict[str, Any]) -> None:
    colour = colour_from_hex(params['colour'])

    role = discord.utils.get(guild.roles, name=target.name)
    if role:
        await role.edit(colour=colour, reason="Update color role")
    else:
        role = await guild.create_role(name=target.name, colour=colour, reason="Create color role")

    await target.add_roles(role)


class ChooseColourOwnItem(ShopItem):
    ITEM_ID = 11
    COST = 60
    DESCRIPTION = "🖌️ Change your own colour"
    AUTO_USE = True
    CATEGORY = "Customise"
    WEB_FORM = (FormField("colour", "Colour", placeholder="#ff8800"),)

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        await set_colour(ctx.guild, ctx.buyer, params)


class ChooseColourOtherItem(ShopItem):
    ITEM_ID = 12
    COST = 300
    DESCRIPTION = "🖌️ Change another user's colour"
    AUTO_USE = True
    CATEGORY = "Customise"
    WEB_FORM = (
        FormField("user", "Target"),
        FormField("colour", "Colour", placeholder="#ff8800"),
    )

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        target = await ctx.guild.fetch_member(params['user'])
        await set_colour(ctx.guild, target, params)


class BlackFridaySaleItem(ShopItem):
    ITEM_ID = 13
    COST = 1800
    DESCRIPTION = "🏷️ Black Friday Sale! Everything half off for the next 30 minutes!"
    AUTO_USE = True
    CATEGORY = "Sale"

    @classmethod
    async def handle_purchase(cls, ctx: ShopContext, params: dict[str, Any]) -> None:
        guild = ctx.guild
        event_name = "Black Friday Sale!"

        existing_event = discord.utils.get(guild.scheduled_events, name=event_name)

        if existing_event:
            await existing_event.delete()

        now = discord.utils.utcnow()
        event_duration = datetime.timedelta(minutes=30)

        start_time = now + datetime.timedelta(seconds=10)
        end_time = start_time + event_duration

        _event = await guild.create_scheduled_event(
            name=event_name,
            start_time=start_time,
            end_time=end_time,
            description="Get half off all shop items!",
            entity_type=discord.EntityType.external,
            privacy_level=discord.PrivacyLevel.guild_only,
            location=guild.name,
        )

        await ctx.announce.send(
            f"<@{ctx.buyer.id}> is starting a sale in 10 seconds! Get 50% off for the next 30 minutes!"
        )


async def get_shop_credit(user_id: int) -> float:
    async with Database(DATABASE_NAME) as db:
        user_list = cast(list[User], await db.select(User, [WhereParam("id", user_id)]))
        if not user_list:
            return 0.0

        user = user_list[0]

        purchases = cast(list[Purchase], await db.select(Purchase, where=[WhereParam("user_id", user_id)]))
        winnings = cast(list[GambleWin], await db.select(GambleWin, where=[WhereParam("user_id", user_id)]))
        bets = cast(list[AdminBet], await db.select(AdminBet, where=[WhereParam("gamble_user_id", user_id)]))

        gifts_sent = cast(list[Gift], await db.select(Gift, where=[WhereParam("giver", user.id)]))
        gifts_received = cast(list[Gift], await db.select(Gift, where=[WhereParam("receiver", user.id)]))

        credit = user.duration
        credit -= sum([p.cost for p in purchases])
        credit -= sum([b.amount for b in bets])
        credit += sum([w.amount for w in winnings])

        credit -= sum([g.amount for g in gifts_sent])
        credit += sum([g.amount for g in gifts_received])

        return credit


async def can_afford_purchase(user: int, cost: int) -> bool:
    credit = await get_shop_credit(user)
    return cost <= credit


async def is_ongoing_sale() -> tuple[bool, datetime.datetime | None]:
    async with Database(DATABASE_NAME) as db:
        sale = cast(list[Purchase], await db.select(Purchase, where=[WhereParam("item_id", BlackFridaySaleItem.ITEM_ID)], order=[OrderParam("timestamp", True)]))
        if not sale:
            return False, None

        end_time = sale[0].timestamp + datetime.timedelta(minutes=30)
        return datetime.datetime.now() < end_time, end_time
