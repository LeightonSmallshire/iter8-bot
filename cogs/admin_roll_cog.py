import operator

import discord
from discord.ext import commands
from discord import app_commands
import logging
from zoneinfo import ZoneInfo
from datetime import time, timedelta
import random, secrets
import asyncio
import utils.bot as bot_utils
import utils.log as log_utils
import utils.database as db_utils

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())



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

        roll_table = bot_utils.get_non_bot_users(interaction)
        roll_table += await db_utils.get_extra_admin_rolls(consume=True)

        new_admin = await bot_utils.do_role_roll(
            interaction, 
            bot_utils.Roles.Admin,
            roll_table,
            "🎲 Let's roll the dice! 🎲", 
            ("<@{}> is dead. Long live <@{}>.", "Long live <@{}>.")
        )

        await db_utils.update_last_admin_roll()

        await asyncio.sleep(2)
        
        roll_table = [x for x in bot_utils.get_non_bot_users(interaction) if x != new_admin]

        await bot_utils.do_role_roll(
            interaction, 
            bot_utils.Roles.BullyTarget,
            roll_table,
            "🎲 Who's getting bullied? 🎲", 
            ("<@{}> is free! <@{}> is the new bully target. GET THEM!", "<@{}> is the new bully target. GET THEM!"),
        )
        
        await asyncio.sleep(2)

        await self.do_gamble_payout(interaction, bot_utils.Users.Nathan)

    async def do_gamble_payout(self, interaction: discord.Interaction, new_admin: int):
        gamble_msg = await interaction.followup.send("Calculating gambling results...", wait=True)

        await asyncio.sleep(2)

        gamble_results = await db_utils.get_gamble_odds(consume_bets=True)
        prize = sum([data["total"] for (_, data)  in gamble_results.items()])

        target_ids = list(gamble_results.keys())
        weights = [gamble_results[uid]["odds"] for uid in target_ids]
        
        if len(gamble_results) > 0:
            winner = random.choices(target_ids, weights=weights, k = 1)[0]
            result = gamble_results[winner]

            lines: list[str] = []
            for user_id, data in result["bettors"].items():
                payout = prize * data["odds"]
                lines.append(f"<@{user_id}> - {timedelta(seconds=round(payout))}")
                await db_utils.payout_gamble(user_id, payout)

            

            gamble_embed = discord.Embed(
                title="Gambling Winnings 💰",
                description="\n".join(lines),
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
