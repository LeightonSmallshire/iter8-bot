import operator

import discord
from discord.ext import commands
from discord import app_commands
import traceback
import logging
import io
import datetime
import utils.bot as bot_utils
import utils.log as log_utils
import utils.database as db_utils
from typing import Iterable

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log'))
_log.addHandler(log_utils.DatabaseHandler())

def _format_rows(headers: list[str], rows: Iterable[tuple]) -> str:
    cols = [headers] + [list(map(lambda x: "" if x is None else str(x), r)) for r in rows]
    if not cols:  # no headers and no rows
        return "No results."
    widths = [max(len(row[i]) for row in cols) for i in range(len(cols[0]))]
    def fmt(row): return " | ".join(val.ljust(widths[i]) for i, val in enumerate(row))
    sep = "-+-".join("-" * w for w in widths)
    lines = [fmt(cols[0]), sep] + [fmt(r) for r in cols[1:]]
    return "```\n" + "\n".join(lines) + "\n```"

    

class DatabaseCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    # --- Slash Command ---

    @app_commands.command(name="sql", description="SQL database operations")
    async def sql_group(self, interaction: discord.Interaction, query: str):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No squeal 4 U")
        
        await interaction.response.defer(ephemeral=True)
        _log.info(f"{interaction.user.name} executed a SQL query: [{query}]")

        try:
            headers, rows = await db_utils.execute_raw_query(query)
        except Exception as e:
            await interaction.followup.send(f"Error: `{type(e).__name__}: {e}`", ephemeral=True)
            return

        if headers is None:  # non-SELECT
            await interaction.followup.send("Query executed.", ephemeral=True)
            return

        text = _format_rows(headers, rows)
        if len(text) <= 1900:
            await interaction.followup.send(text, ephemeral=True)
        else:
            buf = io.StringIO(text.strip("`"))
            file = discord.File(fp=io.BytesIO(buf.getvalue().encode("utf-8")), filename="results.txt")
            await interaction.followup.send(file=file, ephemeral=True)

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
            msg = f'An unhandled command error occurred in cog {self.qualified_name}: {error}'
            _log.error(msg)
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


# --- Cog Setup Function (MANDATORY for extensions) ---

async def setup(bot: commands.Bot):
    await bot.add_cog(DatabaseCog(bot))


# async def teardown(bot: commands.Bot):
#     _log.info(f"Cog '{BotBrokenCog.qualified_name}' unloaded.")
