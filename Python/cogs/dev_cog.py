import asyncio
import glob
import discord
from discord import app_commands
from discord.ext import commands
import utils.bot as bot_utils
import utils.log as log_utils
import utils.files
from typing import Optional
import io
import os
import inspect
import logging
import contextlib
import subprocess
import traceback
import sys

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('data/logs.log', encoding='utf-8'))
_log.addHandler(log_utils.DatabaseHandler())


class DevCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        self.envs: dict[int, dict[str, object]] = {}  # user_id -> locals()
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    @app_commands.command(name='stdout')
    async def get_stdout(self, interaction: discord.Interaction):
        msg = sys.stdout.buf_

        if len(msg) > 1950:
            file = discord.file.File(io.StringIO(msg), 'stdout.log')
            await interaction.response.send_message(file=file, ephemeral=True)
        else:
            await interaction.response.send_message(content=msg, ephemeral=True)

    @app_commands.command(name='logs')
    # @commands.check(bot_utils.is_leighton)
    @app_commands.describe(level="Filter by log level")
    async def get_logs(self, interaction: discord.Interaction, level: Optional[str] = None):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No logs 4 U")

        rows = await log_utils.read_logs(level=level)
        if not rows:
            await interaction.response.send_message("No logs found.", ephemeral=True)
            return

        formatted = []
        for r in rows:
            formatted.append(f"[{r.timestamp:%Y-%m-%d %H:%M:%S}] [{r.level}] {r.message}")

        msg = "```\n" + "\n".join(formatted) + "\n```"
        if len(msg) > 1950:
            file = discord.file.File(io.StringIO(msg), 'database.log')
            await interaction.response.send_message(file=file, ephemeral=True)
        else:
            await interaction.response.send_message(content=msg, ephemeral=True)

    async def autocomplete_path(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        current = os.path.expanduser(os.path.expandvars(current))

        if os.path.isdir(current):
            pattern = os.path.join(current, "*")
        else:
            pattern = f'{current}*'

        choices = [(f'{match}/' if os.path.isdir(match) else match)
                   for match in glob.glob(pattern)]

        return [app_commands.Choice(name=s, value=s) for s in choices]

    @app_commands.command(name='download')
    @app_commands.autocomplete(path=autocomplete_path)
    @commands.check(bot_utils.is_guild_paradise)
    async def do_download(self, interaction: discord.Interaction, path: str):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No files 4 U")

        if os.path.isdir(path):
            zip_dir = utils.files.zip_directory(path)
            file = discord.File(zip_dir, f'{path}.zip')
            return await interaction.response.send_message(file=file, ephemeral=True)

        elif os.path.isfile(path):
            file = discord.File(path)
            return await interaction.response.send_message(file=file, ephemeral=True)
        
    @app_commands.command(name='crash')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_crash(self, interaction: discord.Interaction):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message(f'Stop it {interaction.user.mention}')

        os.abort()
        interaction.response.send_message('past abort somehow - very impressive')

    def get_env(self, uid: int):
        env = self.envs.get(uid)
        if env is None:
            env = {
                "__builtins__": __builtins__,
            }
            self.envs[uid] = env
        return env
    
    async def eval_code(self, src: str, env: dict[str, object]):
        buf = io.StringIO()
        compiled = compile(src, "<expr>", "eval")
        value = eval(compiled, env)
        if inspect.isawaitable(value):
            value = await value
        env["_"] = value
        return repr(value)
        
    async def exec_code(self, src: str, env: dict[str, object]):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exec(compile(src, "<exec>", "exec"), env)

        ret = None
        main = env.get("main")
        if callable(main):
            try:
                if inspect.iscoroutinefunction(main):
                    ret = await main()
                else:
                    maybe = main()
                    if inspect.isawaitable(maybe):
                        ret = await maybe
                    else:
                        ret = maybe
            except TypeError as e:
                # main() requires args; surface a clear error
                raise TypeError("Detected main but it requires arguments") from e
            
        if ret:
            return buf.getvalue() + repr(ret)
        else:
            return buf.getvalue() or "Command completed with no output."

    @app_commands.command(name="exec", description="Execute Python in your persistent REPL.")
    @commands.check(bot_utils.is_guild_paradise)
    @app_commands.describe(code="Code to execute", file="File containing code to execute. Use a main function as entrypoint for async code.")
    async def command_exec(self, interaction,  code: str | None = None, file: discord.Attachment | None = None):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message(f'No REPL 4 U')

        if not code and not file:
            return await interaction.response.send_message("You must provide code or a file to execute.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        env = self.get_env(interaction.user.id)

        src = (await file.read()).decode("utf-8", "ignore") if file else code
        src = src.strip("` \n")

        buf = io.StringIO()
        out = ""
        try:
            try:
                # Try eval first
                out = await self.eval_code(src, env)
            except SyntaxError:
                # Fallback to exec
                out = await self.exec_code(src, env)
        except Exception:
            out = buf.getvalue() + traceback.format_exc()

        if len(out) > 1900:
            out = out[:1900] + "…"
        await interaction.followup.send(f"```\n{out}\n```", ephemeral=True)

    @app_commands.command(name="reset_repl", description="Clear your REPL environment.")
    @commands.check(bot_utils.is_guild_paradise)
    async def reset_env(self, interaction): 
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message(f'No REPL 4 U')
        
        self.envs.pop(interaction.user.id, None)
        await interaction.response.send_message("Environment cleared.", ephemeral=True)

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


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
