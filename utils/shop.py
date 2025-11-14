import discord
import discord.utils
import discord.ui
import datetime
import logging
import secrets
from typing import Callable, Awaitable, Protocol, ClassVar
from .bot import Roles, do_role_roll, get_non_bot_users
from view.components import UserSelect, DurationSelect, ColourSelect, TextSelect


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

        await member.timeout(until, reason=f"<@{ctx.user.id}> used power of the bot. It cannot be contained!.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect()]

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

        await target.timeout(until, reason=f"<@{ctx.user.id}> used the power of the shop.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [UserSelect(), DurationSelect()]

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

        await role.members[0].timeout(until, reason=f"<@{ctx.user.id}> decided to bully the prey of the dice.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect()]

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

        await member.timeout(until, reason=f"<@{ctx.user.id}> decided to bully someone at random.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect()]

class BullyRerollItem(ShopItem):
    ITEM_ID = 3
    COST = 600
    DESCRIPTION = "🎲 Reroll bully target"
    AUTO_USE = True
    CATEGORY = "Timeouts"

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        admin_role = await ctx.guild.fetch_role(Roles.Admin)
        roll_table = [x for x in get_non_bot_users(ctx) if x not in [u.id for u in admin_role.members]]

        await do_role_roll(
            ctx,
            Roles.BullyTarget,
            roll_table,
            f"🎲 <@{ctx.user.id}> is re-rolling the bully target!",
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

        await do_role_roll(
            ctx,
            Roles.Admin,
            roll_table,
            f"🚨 {ctx.user.display_name} called for a reroll! 🚨", 
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>.")            
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

        await current_target.remove_roles(role)
        await new_target.add_roles(role)

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
        pass