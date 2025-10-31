import discord
import discord.utils
import datetime
from typing import Callable, Awaitable
from .model import ShopItem, ShopOptions
from .bot import Users, Roles
from .database import *

PURCHASE_HANDLER_FUNCS: dict[int, Callable[..., Awaitable]] = {}

async def do_purchase(ctx: discord.Interaction, item: ShopItem, params: dict):
    if not item.id in PURCHASE_HANDLER_FUNCS:
        return
    
    return await PURCHASE_HANDLER_FUNCS[item.id](ctx, **params)






def register_shop_handler(id: int):
    """Decorator to register a handler function by id."""
    def decorator(func):
        PURCHASE_HANDLER_FUNCS[id] = func
        return func
    return decorator


@register_shop_handler(ShopOptions.AdminTimeout.id)
async def do_admin_timeout(interaction: discord.Interaction, duration: int):
    role = await interaction.guild.fetch_role(Roles.Admin)
    member = role.members[0]

    start = member.timed_out_until if member.timed_out_until else discord.utils.utcnow()
    until = start + datetime.timedelta(seconds=duration)

    await role.members[0].timeout(until, reason="The power of the bot cannot be contained.")

@register_shop_handler(ShopOptions.UserTimeout.id)
async def do_user_timeout(interaction: discord.Interaction, user: int, duration: int):
    target = await interaction.guild.fetch_member(user)
    
    start = target.timed_out_until if target.timed_out_until else discord.utils.utcnow()
    until = start + datetime.timedelta(seconds=duration)

    await target.timeout(until, reason=f"<@{interaction.user.id}> used the power of the shop.")

@register_shop_handler(ShopOptions.BullyReroll.id)
async def do_bully_reroll(interaction: discord.Interaction):
    role = await interaction.guild.fetch_role(Roles.BullyTarget)
    current_target = role.members[0]
    new_target = Users.random(filter=[current_target.id])

    new_user = interaction.guild.get_member(new_target) or await interaction.guild.fetch_member(new_target)
    
    await current_target.remove_roles(role)
    await new_user.add_roles(role)

@register_shop_handler(ShopOptions.BullyChoose.id)
async def do_bully_choose(interaction: discord.Interaction, user: int):
    role = await interaction.guild.fetch_role(Roles.BullyTarget)
    new_target = await interaction.guild.fetch_member(user)
    current_target = role.members[0]

    await current_target.remove_roles(role)
    await new_target.add_roles(role)

@register_shop_handler(ShopOptions.BullyTimeout.id)
async def do_bully_timeout(interaction: discord.Interaction, duration: int):
    role = await interaction.guild.fetch_role(Roles.BullyTarget)
    member = role.members[0]

    start = member.timed_out_until if member.timed_out_until else discord.utils.utcnow()
    until = start + datetime.timedelta(seconds=duration)

    await role.members[0].timeout(until, reason="Bully the prey of the dice.")

@register_shop_handler(ShopOptions.MakeAdmin.id)
async def do_make_admin(interaction: discord.Interaction):
    role = await interaction.guild.fetch_role(Roles.Admin)
    new_target = await interaction.guild.fetch_member(interaction.user.id)
    current_target = role.members[0]

    await current_target.remove_roles(role)
    await new_target.add_roles(role)

@register_shop_handler(ShopOptions.AdminTicket.id)
async def do_admin_ticket(interaction: discord.Interaction):
    pass

@register_shop_handler(ShopOptions.AdminReroll.id)
async def do_admin_reroll(interaction: discord.Interaction):
    pass
