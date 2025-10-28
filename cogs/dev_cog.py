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
_log.addHandler(log_utils.DatabaseHandler())
_log.addHandler(logging.FileHandler('logs.log'))

class DevCog(commands.Cog):
    def __init__(self, bot: discord.Client):
        super().__init__()
        self.bot_ = bot

    @app_commands.command(name='logs')
    # @commands.check(bot_utils.is_leighton)
    @app_commands.describe(level="Filter by log level")
    async def get_logs(self, interaction: discord.Interaction, level: Optional[str]=None):
        rows = db_utils.read_logs(level=level)
        if not rows:
            await interaction.response.send_message("No logs found.")
            return

        formatted = []
        for r in rows:
            ts = datetime.datetime.fromisoformat(r["timestamp"])
            formatted.append(f"[{ts:%Y-%m-%d %H:%M:%S}] [{r['level']}] {r['message']}")

        msg = "```\n" + "\n".join(formatted) + "\n```"
        await interaction.response.send_message(msg[:2000], ephemeral=True)  # Discord limit
        

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

    # @app_commands.command(name='bash2')
    # # @commands.check(bot_utils.is_leighton)
    # async def do_bash(self, ctx: discord.Interaction, command: str):
    #     if ctx.user.id != bot_utils.Users.Leighton:
    #         return await ctx.response.send_message("No shell 4 U")

    #     await ctx.response.defer(ephemeral=True, thinking=True)

    #     process = await asyncio.create_subprocess_shell(
    #         cmd=command,
    #         stdout=asyncio.PIPE,
    #         stderr=asyncio.PIPE,
    #     )

    #     stdout, stderr = await process.communicate()
    #     return_code = await process.returncode()

    #     stdout = stdout.decode().strip()
    #     stderr = stderr.decode().strip()

    #     message = f'Exit code: {return_code}\n\n{stdout}\n\n{stderr}'

    #     await ctx.followup.send(content=message)


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

#     async def download(self, ctx):
#         pass


async def setup(bot: commands.Bot):
    await bot.add_cog(DevCog(bot))
