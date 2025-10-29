import discord
from discord import app_commands
from discord.ext import commands
import cogs.utils.bot as bot_utils
import cogs.utils.database as db_utils
import cogs.utils.log as log_utils
from typing import Optional
import os
import datetime
import logging

_log = logging.getLogger(__name__)
_log.addHandler(logging.FileHandler('logs.log'))


class DevCog(commands.Cog):
    def __init__(self, client: discord.Client):
        self.bot_ = client
        _log.addHandler(log_utils.DatabaseHandler(client.loop))
        super().__init__()
        _log.info(f"Cog '{self.qualified_name}' initialized.")

    @app_commands.command(name='logs')
    # @commands.check(bot_utils.is_leighton)
    @app_commands.describe(level="Filter by log level")
    async def get_logs(self, interaction: discord.Interaction, level: Optional[str] = None):
        rows = []  # await db_utils.read_logs(level=level)
        if not rows:
            await interaction.response.send_message("No logs found.", ephemeral=True)
            return

        formatted = []
        for r in rows:
            ts = datetime.datetime.fromisoformat(r["timestamp"])
            formatted.append(f"[{ts:%Y-%m-%d %H:%M:%S}] [{r['level']}] {r['message']}")

        msg = "```\n" + "\n".join(formatted) + "\n```"
        await interaction.response.send_message(msg[:2000], ephemeral=True)  # Discord limit

    @app_commands.command(name='download')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_download(self, interaction: discord.Interaction, path: str):
        if not bot_utils.is_trusted_developer(interaction):
            return await interaction.response.send_message("No files 4 U")

        file = discord.File(path)
        await interaction.response.send_message(file=file, ephemeral=True)

    @commands.Cog.listener()
    @commands.check(bot_utils.is_guild_paradise)
    async def on_message(self, message: discord.Message):
        if 'bot broken' in message.content.lower():
            await message.reply('No U')
        if 'boot broekn' in message.content.lower():
            await message.reply('No U booken')

    @app_commands.command(name='crash')
    @commands.check(bot_utils.is_guild_paradise)
    async def do_crash(self, interaction: discord.Interaction):
        if interaction.user.id == bot_utils.Users.Tom:
            await interaction.user.timeout(datetime.timedelta(60), reason='Attemtpting to crash bot')
            return await interaction.response.send_message('Stop it Tom')
        if not bot_utils.is_trusted_developer(interaction):
            await interaction.user.timeout(datetime.timedelta(60), reason='Attemtpting to crash bot')
            return await interaction.response.send_message('No')

        os.abort()
        interaction.response.send_message('past abort somehow')

    # @app_commands.command(name='bash')
    # @commands.check(bot_utils.is_guild_paradise)
    # async def do_bash(self, interaction: discord.Interaction, command: str):
    #     if interaction.user.id != bot_utils.Users.Leighton:
    #         return await interaction.response.send_message("No shell 4 U")
    #
    #     try:
    #         await interaction.response.defer(ephemeral=True, thinking=True)
    #         process = await asyncio.create_subprocess_shell(
    #             cmd=command,
    #             stdout=subprocess.PIPE,
    #             stderr=subprocess.PIPE,
    #         )
    #
    #         stdout, stderr = await process.communicate()
    #         stdout = stdout.decode().strip()
    #         stderr = stderr.decode().strip()
    #
    #         message = f'Command: {command}\n'\
    #             f'Exit code: {process.returncode}\n'\
    #             f'{stdout}\n\n'\
    #             f'{stderr}'
    #
    #         message = f'{message}  - {len(message)}'
    #
    #         # if len(message) < 2000 and not command.startswith('cat'):
    #         #     await interaction.followup.send(content=f'```{message}```'`)
    #         # else:
    #         if True:
    #             files = []
    #
    #             if len(stdout) > 0:
    #                 files.append( discord.File(io.StringIO(stdout), 'stdout.txt'))
    #             if len(stderr) > 0:
    #                 files.append( discord.File(io.StringIO(stderr), 'stderr.txt'))
    #             await interaction.followup.send(content=f'Command: {command}\nExit code: {process.returncode}', files=files)
    #
    #         # await interaction.user.send(content=message)
    #         # await interaction.response.send_message(message, ephemeral=True)
    #         # await interaction.followup.send(message, ephemeral=True)
    #     except BaseException as e:
    #         buf = io.StringIO()
    #         traceback.print_exc(file=buf)
    #         message = f'Event: {e}\nTraceback:\n{buf.read()}'
    #         await interaction.user.send(message)
    #
    #         user = self.bot_.get_user(1416017385596653649)
    #         await interaction.user.send(repr(user))

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


# class FilesystemCog(commands.Cog):
#     def __init__(self, bot):
#         self.bot = bot

#     def _get_file_tree(self, start_dir='.'):
#         output = []
#         EXCLUDED_DIRS = {'.git', '__pycache__',
#                          'venv', 'node_modules', '.idea'}
#         EXCLUDED_FILES = ['.DS_Store', 'Thumbs.db', 'LICENSE', 'README.md']

#         def walk_dir(root, prefix=""):
#             try:
#                 items = os.listdir(root)
#             except Exception:
#                 return

#             dirs = sorted([d for d in items if os.path.isdir(
#                 os.path.join(root, d)) and d not in EXCLUDED_DIRS])
#             files = sorted([f for f in items if os.path.isfile(
#                 os.path.join(root, f)) and f not in EXCLUDED_FILES])

#             all_items = dirs + files

#             for index, item in enumerate(all_items):
#                 path = os.path.join(root, item)
#                 is_last = index == len(all_items) - 1
#                 pointer = "└── " if is_last else "├── "
#                 output.append(f"{prefix}{pointer}{item}")

#                 if os.path.isdir(path):
#                     new_prefix = prefix + ("    " if is_last else "│   ")
#                     walk_dir(path, new_prefix)

#         output.append(f"/{os.path.basename(os.getcwd())}")
#         try:
#             walk_dir(start_dir)
#         except Exception as e:
#             output.append(f"Error accessing directory: {e}")
#         return '\n'.join(output)

#     @app_commands.command(name='filetree', description='Show timeout leaderboards')
#     # @commands.command(name='filetree')
#     # @commands.is_owner()
#     async def file_tree_command(self, ctx):
#         await ctx.defer()
#         file_tree = self._get_file_tree()

#         chunks = [file_tree[i:i + 1990]
#                   for i in range(0, len(file_tree), 1990)]

#         if not chunks:
#             await ctx.author.send("The file tree is empty or could not be generated.")
#             await ctx.send("File tree failed to generate.")
#             return

#         try:
#             await ctx.author.send(f"**File Tree for `{os.getcwd()}`**")
#             for chunk in chunks:
#                 await ctx.author.send(f"```\n{chunk}\n```")
#             await ctx.send("File tree successfully sent to your DMs.")
#         except discord.Forbidden:
#             await ctx.send("I couldn't DM you. Please check your privacy settings to allow DMs from server members.")


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
