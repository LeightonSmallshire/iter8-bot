import discord
import discord.utils
import discord.ui
import datetime
import logging
import secrets
from typing import Callable, Awaitable, Protocol, ClassVar
from .bot import Roles, do_role_roll, get_non_bot_users
from .database import *
from view.components import UserSelect, DurationSelect, ColourSelect, TextSelect


#-----------------------------------------------------------------
#   Shop Items


SHOP_ITEMS = list[type['ShopItem']]()

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
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        raise NotImplementedError()
    
    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return []

class AdminTimeoutItem(ShopItem):
    ITEM_ID = 1
    COST = 120
    DESCRIPTION = "⏱️ Timeout admin (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        duration = params['duration']

        role = await ctx.guild.fetch_role(Roles.Admin)
        member = role.members[0]

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=duration)
        reason = params.get("text", None)

        await member.timeout(until, reason=f"<@{ctx.user.id}> used power of the bot{f' for {reason}' if reason else ''}. It cannot be contained!.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

class UserTimeoutItem(ShopItem):
    ITEM_ID = 2
    COST = 60
    DESCRIPTION = "⏱️ Timeout user (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        target = await ctx.guild.fetch_member(params['user'])
        
        if target.id == ctx.user.id:
            return await ctx.edit_original_response(content='No timeout farming')    
        
        now = discord.utils.utcnow()
        start = max(now, target.timed_out_until) if target.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text", None)
        
        await target.timeout(until, reason=f"<@{ctx.user.id}> used the power of the shop{f' for {reason}' if reason else ''}.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [UserSelect(), DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

class BullyTimeoutItem(ShopItem):
    ITEM_ID = 5
    COST = 30
    DESCRIPTION = "⏱️ Timeout bully target (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        role = await ctx.guild.fetch_role(Roles.BullyTarget)
        member = role.members[0]
        
        if member.id == ctx.user.id:
            return await ctx.edit_original_response('No timeout farming')    

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text", None)

        await role.members[0].timeout(until, reason=f"<@{ctx.user.id}> decided to bully the prey of the dice{f' for {reason}' if reason else ''}.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

class TimeoutRandomItem(ShopItem):
    ITEM_ID = 14
    COST = 30
    DESCRIPTION = "⏱️ Timeout a random target (price per minute)"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        users = get_non_bot_users(ctx)

        index = secrets.randbelow(len(users))

        member = await ctx.guild.fetch_member(users[index])

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])
        reason = params.get("text", None)

        await member.timeout(until, reason=f"<@{ctx.user.id}> decided to bully someone at random{f' for {reason}' if reason else ''}.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect(), TextSelect("Reason", "Enter reason:", "Enter reason...")]

async def make_bully_reroll_table(ctx: discord.Interaction) -> list[int]:
    admin_role = await ctx.guild.fetch_role(Roles.Admin)
    bully_role = await ctx.guild.fetch_role(Roles.BullyTarget)
    filter_users = [u.id for u in admin_role.members] + [u.id for u in bully_role.members if not u.id == ctx.user.id]
    return [x for x in get_non_bot_users(ctx) if x not in filter_users]

class BullyRerollItem(ShopItem):
    ITEM_ID = 3
    COST = 600
    DESCRIPTION = "🎲 Reroll bully target"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
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
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        role = await ctx.guild.fetch_role(Roles.BullyTarget)
        new_target = await ctx.guild.fetch_member(params['user'])
        current_target = role.members[0]
        
        admin_role = await ctx.guild.fetch_role(Roles.Admin)
        if new_target in admin_role.members:
            raise Exception("Can't make the admin the bully target.")

        await current_target.remove_roles(role)
        await new_target.add_roles(role)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [UserSelect()]

class AdminTicketItem(ShopItem):
    ITEM_ID = 7
    COST = 1800
    DESCRIPTION = "🎟️ Add an extra ticket in the next admin dice roll"
    AUTO_USE = False
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        pass

class AdminRerollItem(ShopItem):
    ITEM_ID = 8
    COST = 2700
    DESCRIPTION = "🎲 Reroll the admin"
    AUTO_USE = True
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        roll_table = get_non_bot_users(ctx)

        bully_role = await ctx.guild.fetch_role(Roles.BullyTarget)
        bully_targets = [u.id for u in bully_role.members]

        new_admin = await do_role_roll(
            ctx,
            Roles.Admin,
            roll_table,
            f"🚨 {ctx.user.display_name} called for a reroll! 🚨", 
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>.")            
        )

        if new_admin in bully_targets:
            await do_role_roll(
                ctx,
                Roles.BullyTarget,
                await make_bully_reroll_table(ctx),
                f"🎲 Admin landed on the bully target. Finding a new targe...",
                ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!")      
            )

class MakeAdminItem(ShopItem):
    ITEM_ID = 6
    COST = 7200
    DESCRIPTION = "👑 Make yourself admin"
    AUTO_USE = True
    CATEGORY = "Admin"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        role = await ctx.guild.fetch_role(Roles.Admin)
        new_target = await ctx.guild.fetch_member(ctx.user.id)
        current_target = role.members[0]

        bully_role = await ctx.guild.fetch_role(Roles.BullyTarget)
        bully_targets = [u.id for u in bully_role.members]

        await current_target.remove_roles(role)
        await new_target.add_roles(role)

        if ctx.user.id in bully_targets:
            await do_role_roll(
                ctx,
                Roles.BullyTarget,
                await make_bully_reroll_table(ctx),
                f"🎲 Admin landed on the bully target. Finding a new targe...",
                ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!")      
            )

class ChooseNicknameOwnItem(ShopItem):
    ITEM_ID = 9
    COST = 60
    DESCRIPTION = "✏️ Change your own nickname"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        new_nick = params['text']
        member = await ctx.guild.fetch_member(ctx.user.id)
        await member.edit(nick=new_nick)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [TextSelect(title="Enter a new nickame", label="Nickname", placeholder="Enter a username...")]
    
class ChooseNicknameOtherItem(ShopItem):
    ITEM_ID = 10
    COST = 300
    DESCRIPTION = "✏️ Change another user's nickname"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        new_nick = params['text']
        target = await ctx.guild.fetch_member(params['user'])
        await target.edit(nick=new_nick)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [
            UserSelect(),
            TextSelect(title="Enter a new nickame", label="Nickname", placeholder="Enter a username...")
        ]
    

def colour_from_hex(code: str) -> discord.Color:
    code = code.lstrip('#')
    if len(code) == 3:  # expand #RGB -> #RRGGBB
        code = ''.join(ch*2 for ch in code)
    return discord.Color(int(code, 16))

async def set_colour(ctx: discord.Interaction, target: discord.Member, params: dict):
    colour = colour_from_hex(params['colour'])

    role = discord.utils.get(ctx.guild.roles, name=target.name)
    if role:
        await role.edit(colour=colour, reason="Update color role")
    else:
        # parameter name is 'colour' in discord.py
        role = await ctx.guild.create_role(name=target.name, colour=colour, reason="Create color role")

    await target.add_roles(role)

class ChooseColourOwnItem(ShopItem):
    ITEM_ID = 11
    COST = 60
    DESCRIPTION = "🖌️ Change your own colour"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        await set_colour(ctx, ctx.user, params)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [ColourSelect()]

class ChooseColourOtherItem(ShopItem):
    ITEM_ID = 12
    COST = 300
    DESCRIPTION = "🖌️ Change another user's colour"
    AUTO_USE = True
    CATEGORY = "Customise"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        target = await ctx.guild.fetch_member(params['user'])
        await set_colour(ctx, target, params)

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
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
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        event_name = "Black Friday Sale!"
        now = discord.utils.utcnow()
        event_duration = datetime.timedelta(minutes=30)
        
        # Check if the event already exists
        existing_event = discord.utils.get(ctx.guild.scheduled_events, name=event_name)
        
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

            event = await ctx.guild.create_scheduled_event(
                name=event_name,
                start_time=start_time,
                end_time=end_time,
                description="Get half off all shop items!",
                entity_type=discord.EntityType.external,
                privacy_level=discord.PrivacyLevel.guild_only,
                location=f"{ctx.guild.name}"
            )

            await ctx.followup.send(
            f"<@{ctx.user.id}> started a sale! Get 50% off for the next 30 minutes!"
            )










#-----------------------------------------------------------------
#   Database Access
            
async def get_shop_credit(user_id: int) -> float:
    async with Database(DATABASE_NAME) as db:
        user = await db.select(User, [WhereParam("id", user_id)])
        if not user:
            return 0
        
        user = user[0]

        purchases = await db.select(Purchase, where=[WhereParam("user_id", user_id)])

        winnings = await db.select(GambleWin, where=[WhereParam("user_id", user_id)])
        bets = await db.select(AdminBet, where=[WhereParam("gamble_user_id", user_id)])

        gifts_sent = await db.select(Gift, where=[WhereParam("giver", user.id)])
        gifts_received  = await db.select(Gift, where=[WhereParam("receiver", user.id)])

        stock_unfulfilled = await db.select(Trade, where=[WhereParam("user_id", user.id), WhereParam("sold_at", None, "IS")])
        stock_fulfilled_long = await db.select(Trade, where=[WhereParam("user_id", user.id), WhereParam("sold_at", None, "IS NOT"), WhereParam("short", False)])
        stock_fulfilled_short = await db.select(Trade, where=[WhereParam("user_id", user.id), WhereParam("sold_at", None, "IS NOT"), WhereParam("short", True)])

        credit = user.duration

        credit -= sum([p.cost for p in purchases])

        credit -= sum([b.amount for b in bets])
        credit += sum([w.amount for w in winnings])

        credit -= sum([g.amount for g in gifts_sent])
        credit += sum([g.amount for g in gifts_received])

        credit -= sum([s.bought_at * s.count for s in stock_unfulfilled])
        credit += sum([(s.sold_at - s.bought_at) * s.count for s in stock_fulfilled_long])
        credit -= sum([(s.sold_at - s.bought_at) * s.count for s in stock_fulfilled_short])

        return credit

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