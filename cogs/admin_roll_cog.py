import operator

import discord
from discord.ext import commands
from discord import app_commands
import logging
from zoneinfo import ZoneInfo
from datetime import time, timedelta
import random
import asyncio
import utils.bot as bot_utils
import utils.log as log_utils
import utils.database as db_utils

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


ROLL_GIF_URL = "https://media.tenor.com/XYkAxffY_PsAAAAM/dice-bae-dice.gif"

def is_correct_time(interaction: discord.Interaction) -> bool:
    UK = ZoneInfo("Europe/London")
    dt_utc = interaction.created_at
    dt_uk = dt_utc.astimezone(UK)

    return dt_uk.weekday() == 4 and dt_uk.time() >= time(13, 0)

async def is_first_roll(interaction: discord.Interaction) -> bool:
    UK = ZoneInfo("Europe/London")
    dt_utc = interaction.created_at

    roll_info = await db_utils.get_last_admin_roll()
    time_passed = (dt_utc - roll_info.last_roll) > timedelta(days=6) if roll_info else True

    return time_passed

def make_emoji_number(num: int):
    return "".join([f":number_{d}:" for d in str(num)])

class AdminRollCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='roll_admin', description='Commence the weekly admin dice roll.')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_roll_admin(self, interaction: discord.Interaction):
        if not is_correct_time(interaction):
            await interaction.response.send_message(f"Wait till you've had your samosa!")
            return

        if not await is_first_roll(interaction):
            await interaction.response.send_message(f"The dice has already been rolled, respect its result (unless you have a reroll token).")
            return
        
        await interaction.response.defer()

        new_admin = await self.do_roll(
            interaction, 
            bot_utils.Roles.Admin, 
            "🎲 Let's roll the dice! 🎲", 
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>."),
            extra_tickets=True
        )

        await db_utils.update_last_admin_roll()

        await asyncio.sleep(2)

        await self.do_roll(
            interaction, 
            bot_utils.Roles.BullyTarget, 
            "🎲 Who's getting bullied? 🎲", 
            ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!"),
            extra_tickets=False,
            filter_users=[new_admin]
        )
        
        await asyncio.sleep(2)

        await self.do_gamble_payout(interaction, new_admin)


    @app_commands.command(name='reroll', description='Use a purchased reroll token to re-roll the admin.')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_reroll_admin(self, interaction: discord.Interaction):
        allowed, reason = await db_utils.use_admin_reroll_token(interaction.user.id)
        if not allowed:
            await interaction.response.send_message(reason)
            return

        await interaction.response.defer()
        await self.do_roll(
            interaction, 
            bot_utils.Roles.Admin, 
            f"🚨 {interaction.user.display_name} called for a reroll! 🚨", 
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>."),
            extra_tickets=False
        )

    async def do_roll(self, interaction:discord.Interaction, role_id: int, embed_title: str, response: tuple[str, str], extra_tickets: bool, filter_users: list[int] = []):
        role = interaction.guild.get_role(role_id) or await interaction.guild.fetch_role(role_id)
        prev_user = role.members[0] if role.members else None

        roll_table = [x.id for x in interaction.guild.members if x.id not in filter_users]
        if (extra_tickets):
            roll_table += await db_utils.get_extra_admin_rolls(consume=True)
        roll_table = await bot_utils.filter_bots(interaction, roll_table)

        list_embed = discord.Embed(title=embed_title, color=discord.Color.yellow())
        for idx, user_id in enumerate(roll_table, 1):
            list_embed.add_field(
                name=make_emoji_number(idx),
                value=f"<@{user_id}>",
                inline=False,
            )

        await interaction.followup.send(embed=list_embed)

        if not roll_table:
            await interaction.followup.send(content="There are no users for this roll.")
            return 0
        
        await asyncio.sleep(3)

        roll_embed = discord.Embed(title="Rolling...")
        roll_embed.set_image(url=ROLL_GIF_URL)

        msg = await interaction.followup.send(embed=roll_embed, wait=True)

        # Sleep for dramatic effect
        await asyncio.sleep(4)

        index = random.randrange(0, len(roll_table))
        await msg.edit(content=f"A {make_emoji_number(index + 1)} was rolled!", embed=None)

        await asyncio.sleep(3)

        choice = roll_table[index]
        new_user = await interaction.guild.fetch_member(choice)

        if prev_user is not None:
            await prev_user.remove_roles(role)

        await new_user.add_roles(role)

        message_contents = response[0].format(prev_user.id, choice) if prev_user else response[1].format(choice)
        await msg.edit(content=message_contents)

        return new_user.id


    async def do_gamble_payout(self, interaction: discord.Interaction, new_admin: int):
        gamble_msg = await interaction.followup.send("Calculating gambling results...", wait=True)

        await asyncio.sleep(2)

        gamble_results = await db_utils.get_gamble_results(new_admin)
        if len(gamble_results) > 0:
            gamble_embed = discord.Embed(
                title="Gambling Winnings 💰",
                description="\n".join([f"<@{user_id}> - {timedelta(seconds=round(amount))}" for (user_id, amount) in gamble_results.items()]),
                color=discord.Color.green(),
            )
            await gamble_msg.edit(content=None, embed=gamble_embed)
        else:
            await gamble_msg.edit(content="No gambling winnings this time. What a bunch of losers!")


    # --- Local Command Error Handler (Overrides the global handler for this cog's commands) ---

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError) -> None:
        """
        Handles errors specifically for commands defined within this cog.
        Note: This specific function is for handling prefix command errors.
        For slash commands, errors are often handled via `on_app_command_error`.
        """
        if isinstance(error, commands.MissingPermissions):
            await interaction.response.send_message(f"You don't have the necessary permissions to run this command.")
        elif isinstance(error, commands.CommandNotFound):
            # This generally won't happen if the command is correctly registered
            pass
        else:
            _log.error(f'An unhandled command error occurred in cog {self.qualified_name}: {error}')

# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(AdminRollCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
