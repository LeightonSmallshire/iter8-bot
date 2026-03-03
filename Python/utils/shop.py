from __future__ import annotations

import datetime
import secrets
from typing import Any, Dict, List, Optional, Type

import discord

from .bot import Roles, do_role_roll, get_non_bot_users, on_new_admin
from .database import DATABASE_NAME, Database, OrderParam, WhereParam
from .model import AdminBet, GambleWin, Gift, Purchase, User
from view.components import ColourSelect, DurationSelect, TextSelect, UserSelect


#-----------------------------------------------------------------
#   Shop Items


SHOP_ITEMS: list[type["ShopItem"]] = []

class ShopItem:
    ITEM_ID: int
    COST: int
    DESCRIPTION: str
    AUTO_USE: bool
    CATEGORY: str

    def __init_subclass__(cls) -> None:
        assert hasattr(cls, 'ITEM_ID') and isinstance(cls.ITEM_ID, int)
        assert hasattr(cls, 'COST') and isinstance(cls.COST, int)
        assert hasattr(cls, 'DESCRIPTION') and isinstance(cls.DESCRIPTION, str)
        assert hasattr(cls, 'AUTO_USE') and isinstance(cls.AUTO_USE, bool)
        assert hasattr(cls, 'CATEGORY') and isinstance(cls.CATEGORY, str)
        
        SHOP_ITEMS.append(cls)

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        raise NotImplementedError()
    
    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return []

class AdminTimeoutItem(ShopItem):
    ITEM_ID = 1
    COST = 120
    DESCRIPTION = "⏱️ Timeout admin (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        duration = params["duration"]

        role = await guild.fetch_role(Roles.Admin)
        member = role.members[0]

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=duration)
        reason = params.get("text", None)

        await member.timeout(until, reason=f"<@{ctx.user.id}> used power of the bot{f' for {reason}' if reason else ''}. It cannot be contained!.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

class UserTimeoutItem(ShopItem):
    ITEM_ID = 2
    COST = 60
    DESCRIPTION = "⏱️ Timeout user (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        target = await guild.fetch_member(params["user"])

        if target.id == ctx.user.id:
            await ctx.edit_original_response(content="No timeout farming")
            return
        
        now = discord.utils.utcnow()
        start = max(now, target.timed_out_until) if target.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text", None)
        
        await target.timeout(until, reason=f"<@{ctx.user.id}> used the power of the shop{f' for {reason}' if reason else ''}.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [UserSelect(), DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

class BullyTimeoutItem(ShopItem):
    ITEM_ID = 5
    COST = 30
    DESCRIPTION = "⏱️ Timeout bully target (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        role = await guild.fetch_role(Roles.BullyTarget)
        member = role.members[0]
        
        if member.id == ctx.user.id:
            await ctx.edit_original_response(content="No timeout farming")
            return

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text", None)

        await role.members[0].timeout(until, reason=f"<@{ctx.user.id}> decided to bully the prey of the dice{f' for {reason}' if reason else ''}.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

class TimeoutRandomItem(ShopItem):
    ITEM_ID = 14
    COST = 30
    DESCRIPTION = "⏱️ Timeout a random target (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        users = get_non_bot_users(ctx)

        index = secrets.randbelow(len(users))

        member = await guild.fetch_member(users[index])

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text", None)

        await member.timeout(until, reason=f"<@{ctx.user.id}> decided to bully someone at random{f' for {reason}' if reason else ''}.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

async def make_bully_reroll_table(ctx: discord.Interaction) -> list[int]:
    guild = ctx.guild
    if guild is None:
        return []
    admin_role = await guild.fetch_role(Roles.Admin)
    bully_role = await guild.fetch_role(Roles.BullyTarget)
    filter_users = [u.id for u in admin_role.members] + [u.id for u in bully_role.members if not u.id == ctx.user.id]
    return [x for x in get_non_bot_users(ctx) if x not in filter_users]

class BullyRerollItem(ShopItem):
    ITEM_ID = 3
    COST = 600
    DESCRIPTION = "🎲 Reroll bully target"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        await do_role_roll(
            ctx,
            Roles.BullyTarget,
            await make_bully_reroll_table(ctx),
            f"🎲 {ctx.user.display_name} is re-rolling the bully target!",
            ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!")
        )

class BullyChooseItem(ShopItem):
    ITEM_ID = 4
    COST = 1200
    DESCRIPTION = "🤕 Choose bully target"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        role = await guild.fetch_role(Roles.BullyTarget)
        new_target = await guild.fetch_member(params["user"])
        current_target = role.members[0]
        
        admin_role = await guild.fetch_role(Roles.Admin)
        if new_target in admin_role.members:
            raise Exception("Can't make the admin the bully target.")

        await current_target.remove_roles(role)
        await new_target.add_roles(role)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [UserSelect()]

class AdminTicketItem(ShopItem):
    ITEM_ID = 7
    COST = 1800
    DESCRIPTION = "🎟️ Add an extra ticket in the next admin dice roll"
    AUTO_USE = False
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        pass

class AdminRerollItem(ShopItem):
    ITEM_ID = 8
    COST = 2700
    DESCRIPTION = "🎲 Reroll the admin"
    AUTO_USE = True
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        roll_table = get_non_bot_users(ctx)

        bully_role = await guild.fetch_role(Roles.BullyTarget)
        bully_targets = [u.id for u in bully_role.members]

        new_admin = await do_role_roll(
            ctx,
            Roles.Admin,
            roll_table,
            f"🚨 {ctx.user.display_name} called for a reroll! 🚨", 
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>.")            
        )
        await on_new_admin(ctx, new_admin)

        if new_admin in bully_targets:
            await do_role_roll(
                ctx,
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
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        role = await guild.fetch_role(Roles.Admin)
        new_target = await guild.fetch_member(ctx.user.id)

        for member in role.members:
            await member.remove_roles(role)

        await new_target.add_roles(role)
        await on_new_admin(ctx, new_target.id)

        await ctx.followup.send(content=f"@everyone {ctx.user.mention} just made themselves an Admin!", allowed_mentions=discord.AllowedMentions(roles=True))

        bully_role = await guild.fetch_role(Roles.BullyTarget)
        bully_targets = [u.id for u in bully_role.members]

        if ctx.user.id in bully_targets:
            await do_role_roll(
                ctx,
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

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        new_nick = params["text"]
        member = await guild.fetch_member(ctx.user.id)
        await member.edit(nick=new_nick)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [TextSelect(title="Enter a new nickame", label="Nickname", placeholder="Enter a username...")]
    
class ChooseNicknameOtherItem(ShopItem):
    ITEM_ID = 10
    COST = 300
    DESCRIPTION = "✏️ Change another user's nickname"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        new_nick = params["text"]
        target = await guild.fetch_member(params["user"])
        await target.edit(nick=new_nick)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [
            UserSelect(),
            TextSelect(title="Enter a new nickame", label="Nickname", placeholder="Enter a username...")
        ]
    

def colour_from_hex(code: str) -> discord.Color:
    code = code.lstrip('#')
    if len(code) == 3:  # expand #RGB -> #RRGGBB
        code = ''.join(ch*2 for ch in code)
    return discord.Color(int(code, 16))

async def set_colour(ctx: discord.Interaction, target: discord.Member, params: Dict[str, Any]) -> None:
    colour = colour_from_hex(params['colour'])

    guild = ctx.guild
    if guild is None:
        return

    role = discord.utils.get(guild.roles, name=target.name)
    if role:
        await role.edit(colour=colour, reason="Update color role")
    else:
        # parameter name is 'colour' in discord.py
        role = await guild.create_role(name=target.name, colour=colour, reason="Create color role")

    await target.add_roles(role)

class ChooseColourOwnItem(ShopItem):
    ITEM_ID = 11
    COST = 60
    DESCRIPTION = "🖌️ Change your own colour"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        member = await guild.fetch_member(ctx.user.id)
        await set_colour(ctx, member, params)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [ColourSelect()]

class ChooseColourOtherItem(ShopItem):
    ITEM_ID = 12
    COST = 300
    DESCRIPTION = "🖌️ Change another user's colour"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        guild = ctx.guild
        if guild is None:
            return

        target = await guild.fetch_member(params["user"])
        await set_colour(ctx, target, params)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item[Any]]:
        return [
            UserSelect(),
            ColourSelect(),
        ]
    
class BlackFridaySaleItem(ShopItem):
    ITEM_ID = 13
    COST = 1800
    DESCRIPTION = "🏷️ Black Friday Sale! Everything half off for the next 30 minutes!"
    AUTO_USE = True
    CATEGORY = "Sale"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: Dict[str, Any]) -> None:
        event_name = "Black Friday Sale!"
        now = discord.utils.utcnow()
        event_duration = datetime.timedelta(minutes=30)
        
        # Check if the event already exists
        guild = ctx.guild
        if guild is None:
            return

        existing_event = discord.utils.get(guild.scheduled_events, name=event_name)
        
        if existing_event:
            # Update the end time
            new_end = (existing_event.end_time or now) + event_duration

            await existing_event.edit(end_time=new_end)

            await ctx.followup.send(
                f"The Black Friday Sale was extended by @<{ctx.user.id}> by another 30 minutes!"
            )
        else:
            start_time = now
            end_time = now + event_duration

            event = await guild.create_scheduled_event(
                name=event_name,
                start_time=start_time,
                end_time=end_time,
                description="Get half off all shop items!",
                entity_type=discord.EntityType.external,
                privacy_level=discord.PrivacyLevel.guild_only,
                location=f"{guild.name}"
            )

            await ctx.followup.send(
            f"<@{ctx.user.id}> started a sale! Get 50% off for the next 30 minutes!"
            )










#-----------------------------------------------------------------
#   Database Access
            
async def get_shop_credit(user_id: int) -> float:
    async with Database(DATABASE_NAME) as db:
        user_any = await db.select(User, [WhereParam("id", user_id)])
        users = list(user_any) if isinstance(user_any, list) else [user_any] if user_any else []
        if not users:
            return 0
        
        user = users[0]

        purchases_any = await db.select(Purchase, where=[WhereParam("user_id", user_id)])
        winnings_any = await db.select(GambleWin, where=[WhereParam("user_id", user_id)])
        bets_any = await db.select(AdminBet, where=[WhereParam("gamble_user_id", user_id)])
        gifts_sent_any = await db.select(Gift, where=[WhereParam("giver", user.id)])
        gifts_received_any = await db.select(Gift, where=[WhereParam("receiver", user.id)])

        purchases: list[Purchase] = list(purchases_any) if isinstance(purchases_any, list) else [purchases_any]
        winnings: list[GambleWin] = list(winnings_any) if isinstance(winnings_any, list) else [winnings_any]
        bets: list[AdminBet] = list(bets_any) if isinstance(bets_any, list) else [bets_any]
        gifts_sent: list[Gift] = list(gifts_sent_any) if isinstance(gifts_sent_any, list) else [gifts_sent_any]
        gifts_received: list[Gift] = list(gifts_received_any) if isinstance(gifts_received_any, list) else [gifts_received_any]

        # stock_unfulfilled = await db.select(Trade, where=[WhereParam("user_id", user.id), WhereParam("sold_at", None, "IS")])
        # stock_fulfilled_long = await db.select(Trade, where=[WhereParam("user_id", user.id), WhereParam("sold_at", None, "IS NOT"), WhereParam("short", False)])
        # stock_fulfilled_short = await db.select(Trade, where=[WhereParam("user_id", user.id), WhereParam("sold_at", None, "IS NOT"), WhereParam("short", True)])

        credit = user.duration

        credit -= sum([p.cost for p in purchases])

        credit -= sum([b.amount for b in bets])
        credit += sum([w.amount for w in winnings])

        credit -= sum([g.amount for g in gifts_sent])
        credit += sum([g.amount for g in gifts_received])

        # credit -= sum([s.bought_at * s.count for s in stock_unfulfilled])
        # credit += sum([(s.sold_at - s.bought_at) * s.count for s in stock_fulfilled_long])
        # credit -= sum([(s.sold_at - s.bought_at) * s.count for s in stock_fulfilled_short])

        return float(credit)

async def can_afford_purchase(user: int, cost: int) -> bool:
    credit = await get_shop_credit(user)
    return cost <= credit

async def is_ongoing_sale() -> tuple[bool, Optional[datetime.datetime]]:
    async with Database(DATABASE_NAME) as db:
        sale = await db.select(Purchase, where=[WhereParam("item_id", BlackFridaySaleItem.ITEM_ID)], order=[OrderParam("timestamp", True)])
        if not sale:
            return False, None
        
        end_time = sale[0].timestamp + datetime.timedelta(minutes=30)
        return datetime.datetime.now() < end_time, end_time