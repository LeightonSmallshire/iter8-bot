import operator

import discord
from discord.ext import commands
from discord import app_commands
import logging
import random
import asyncio
import utils.bot as bot_utils
import utils.log as log_utils
import utils.database as db_utils

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())


class AdminRollCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name='roll_admin', description='Commence the weekly admin dice roll.')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_roll_admin(self, interaction: discord.Interaction):
        if not await bot_utils.is_user_role(interaction, bot_utils.Roles.DiceRoller):
            await interaction.response.send_message(f"Only <@&{bot_utils.Roles.DiceRoller}> may roll the admin.")
            return

        await self.do_admin_roll(interaction, False)


    @app_commands.command(name='reroll', description='Use a purchased reroll token to re-roll the admin.')
    @commands.check(bot_utils.is_guild_paradise)
    async def command_reroll_admin(self, interaction: discord.Interaction):
        allowed, reason = await db_utils.use_admin_reroll_token(interaction.user.id)
        if not allowed:
            await interaction.response.send_message(reason)
            return

        await self.do_admin_roll(interaction, True)



    async def do_admin_roll(self, interaction: discord.Interaction, reroll: bool):
        await interaction.response.defer()

        admin = interaction.guild.get_role(bot_utils.Roles.Admin) or await interaction.guild.fetch_role(bot_utils.Roles.Admin)
        prev_admin = admin.members[0]

        roll_table = [x.id for x in interaction.guild.members]
        roll_table += await db_utils.get_extra_admin_rolls()
        roll_table = await bot_utils.filter_bots(interaction, roll_table)
        
        title = "🎲 Let's roll the dice! 🎲" if not reroll else f"🚨 {interaction.user.display_name} called for a reroll! 🚨"

        def make_emoji_number(num: int):
            return "".join([f":number_{d}:" for d in str(num)])

        embed = discord.Embed(title=title, color=discord.Color.yellow())
        for idx, user_id in enumerate(roll_table, 1):
            embed.add_field(
                name=make_emoji_number(idx),
                value=f"<@{user_id}>",
                inline=False,
            )

        await interaction.followup.send(embed=embed)
        msg = await interaction.followup.send("Rolling...", wait=True)

        # Sleep for dramatic effect
        await asyncio.sleep(3)

        index = random.randrange(0, len(roll_table))
        await msg.edit(content=f"A :number_{make_emoji_number(index)}: was rolled")

        await asyncio.sleep(1)

        choice = roll_table[index]
        new_admin = await interaction.guild.fetch_member(choice)

        await new_admin.add_roles(admin)
        await prev_admin.remove_roles(admin)

        await msg.edit(content=f"<@{prev_admin.id}> is dead. Long live <@{choice}>")


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
