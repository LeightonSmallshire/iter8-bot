import discord
import discord.utils
import discord.ui
import datetime
from typing import Callable, Awaitable, Protocol, ClassVar
from .bot import Users, Roles
from view.components import UserSelect, DurationSelect, ColourSelect, TextSelect

SHOP_ITEMS = list[type['ShopItem']]()

class ShopItem:
    ITEM_ID: int
    COST: int
    DESCRIPTION: str
    AUTO_USE: bool

    def __init_subclass__(cls) -> None:
        assert hasattr(cls, 'ITEM_ID') and isinstance(cls.ITEM_ID, int)
        assert hasattr(cls, 'COST') and isinstance(cls.COST, int)
        assert hasattr(cls, 'DESCRIPTION') and isinstance(cls.DESCRIPTION, str)
        assert hasattr(cls, 'AUTO_USE') and isinstance(cls.AUTO_USE, bool)
        
        SHOP_ITEMS.append(cls)

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        raise NotImplementedError()
    
    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return []

class AdminTimeoutItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 300
    DESCRIPTION = "⏱️ Timeout admin (price per minute)"
    AUTO_USE = True

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        duration = params['duration']

        role = await ctx.guild.fetch_role(Roles.Admin)
        member = role.members[0]

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=duration)

        await role.members[0].timeout(until, reason="The power of the bot cannot be contained.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect()]

class UserTimeoutItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 60
    DESCRIPTION = "⏱️ Timeout admin (price per minute)"
    AUTO_USE = True

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        target = await ctx.guild.fetch_member(params['user'])
        
        if target.id == ctx.user.id:
            return await ctx.response.send_message('No timeout farming')    
        
        now = discord.utils.utcnow()
        start = max(now, target.timed_out_until) if target.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])

        await target.timeout(until, reason=f"<@{ctx.user.id}> used the power of the shop.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [UserSelect(), DurationSelect()]

class BullyRerollItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 1800
    DESCRIPTION = "🎲 Reroll bully target"
    AUTO_USE = True

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        role = await ctx.guild.fetch_role(Roles.BullyTarget)
        current_target = role.members[0]
        new_target = Users.random(filter=[current_target.id])

        new_user = ctx.guild.get_member(new_target) or await ctx.guild.fetch_member(new_target)
        
        await current_target.remove_roles(role)
        await new_user.add_roles(role)

class BullyChooseItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 3600
    DESCRIPTION = "🤕 Choose bully target"
    AUTO_USE = True

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

class BullyTimeoutItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 30
    DESCRIPTION = "⏱️ Timeout bully target (price per minute)"
    AUTO_USE = True

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        role = await ctx.guild.fetch_role(Roles.BullyTarget)
        member = role.members[0]
        
        if member.id == ctx.user.id:
            return await ctx.response.send_message('No timeout farming')    

        now = discord.utils.utcnow()
        start = max(now, member.timed_out_until) if member.timed_out_until else now
        until = start + datetime.timedelta(minutes=params['duration'])

        await role.members[0].timeout(until, reason="Bully the prey of the dice.")

    @classmethod
    def get_input_handlers(cls) -> list[discord.ui.Item]:
        return [DurationSelect()]

class MakeAdminItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 18000
    DESCRIPTION = "👑 Make yourself admin"
    AUTO_USE = True

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        role = await ctx.guild.fetch_role(Roles.Admin)
        new_target = await ctx.guild.fetch_member(ctx.user.id)
        current_target = role.members[0]

        await current_target.remove_roles(role)
        await new_target.add_roles(role)

class AdminTicketItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 3600
    DESCRIPTION = "🎟️ Add an extra ticket in the next admin dice roll"
    AUTO_USE = False

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        pass

class AdminRerollItem(ShopItem):
    ITEM_ID = len(SHOP_ITEMS) + 1
    COST = 3600
    DESCRIPTION = "🎲 Reroll the admin dice roll"
    AUTO_USE = False

    @classmethod
    async def handle_purchase(cls, ctx: discord.Interaction, params: dict):
        pass
