import os
import dotenv

import logfire
import utils.bot as bot_utils
import utils.database as db_utils
import utils.stocks.stock_db as stock_utils
import discord
import datetime
import traceback

from discord.ext import commands


dotenv.load_dotenv('data/.env')
dotenv.load_dotenv()

# CD to here always
os.chdir(os.path.dirname(__file__))

# --- Configuration ---
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]

COGS_DIR = "cogs"

IS_LIVE = os.path.exists('/.dockerenv')
IS_TESTING = not IS_LIVE

os.makedirs('data', exist_ok=True)

# --- Logfire Setup ---
logfire.configure()
logger = logfire


now = datetime.datetime.now().time()
is_work_hours = datetime.time(7, 30) <= now <= datetime.time(19, 0)


class HotReloadBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def on_ready(self):
        logger.info(f'Discord Bot logged in as {self.user} (ID: {self.user.id})')

        if is_work_hours and IS_LIVE:
            message = f'Bot connected {read_git_head()}'
            bot_utils.defer_message(self, bot_utils.Users.Leighton, message)
            bot_utils.defer_message(self, bot_utils.Users.Nathan, message)

        server = discord.utils.get(self.guilds, id=bot_utils.Guilds.Default)
        leaderboard = await bot_utils.get_timeout_data(server)
        await db_utils.init_database(leaderboard, stock_utils.AVAILABLE_STOCKS)

        self.tree.error(self._handle_error)
        await self.hot_reload_cogs()

    async def hot_reload_cogs(self):
        """Unloads, reloads, and reports the status of all cogs."""

        logger.info('--- Loading cogs ---')

        reloaded_cogs = []
        failed_cogs = []

        # 1. Re-scan the directory to find all current cog files after git pull
        current_cogs = []
        for filename in os.listdir(COGS_DIR):
            if filename.endswith(".py") and filename != "__init__.py":
                current_cogs.append(f"{COGS_DIR}.{filename[:-3]}")

        # 2. Perform reload/load operations
        for cog_name in current_cogs:
            try:
                if cog_name in self.extensions:
                    await self.reload_extension(cog_name)
                    logger.info(f'Successfully reloaded cog: {cog_name}')
                else:
                    await self.load_extension(cog_name)
                    logger.info(f'Successfully loaded NEW cog: {cog_name}')
                reloaded_cogs.append(cog_name)
            except Exception as e:
                logger.error(f'Failed to reload/load cog {cog_name} {e}')
                failed_cogs.append(f'{cog_name} {e}')

        # 3. Check for removed cogs
        unloaded_cogs = []
        for ext_name in list(self.extensions.keys()):
            if ext_name.startswith(f'{COGS_DIR}.') and ext_name not in current_cogs:
                try:
                    await self.unload_extension(ext_name)
                    unloaded_cogs.append(ext_name)
                    logger.info(f'Successfully unloaded REMOVED cog: {ext_name}')
                except Exception as e:
                    logger.error(f'Failed to unload removed cog {ext_name}: {e}')

        # 4. Syncing
        logger.info('Syncing...')
        self.tree.copy_global_to(guild=discord.Object(id=bot_utils.Guilds.Default))
        synced = await self.tree.sync(guild=discord.Object(id=bot_utils.Guilds.Default))
        logger.info(f'Synced {len(synced)} commands.')

        # 5. Build Discord-formatted message
        lines = ["## 🔄 Cog Reload Report"]

        if failed_cogs:
            lines.append(f"### ❌ Failures ({len(failed_cogs)})")
            lines.append("```python")
            lines.extend(failed_cogs)
            lines.append("```")

        if reloaded_cogs:
            lines.append(f"### ✅ Success ({len(reloaded_cogs)})")
            # Format as a compact list
            reloaded_names = ", ".join([c.split('.')[-1] for c in reloaded_cogs])
            lines.append(f"**Cogs:** {reloaded_names}")

        if unloaded_cogs:
            lines.append(f"### 🗑️ Unloaded ({len(unloaded_cogs)})")
            lines.append(f"Cleanup: {', '.join([u.split('.')[-1] for u in unloaded_cogs])}")

        lines.append(f"\n⚡ **Commands Synced:** `{len(synced)}`")

        formatted_report = "\n".join(lines)

        # 6. Final reporting
        status = {
            'status': 'Cogs reloaded' if not failed_cogs else 'Reloaded with errors',
            'reloaded': reloaded_cogs,
            'failed': failed_cogs,
            'synced': [str(c) for c in synced]
        }

        # if is_work_hours and IS_LIVE:
        bot_utils.defer_message(self, bot_utils.Users.Leighton, formatted_report)

        return status

    async def _handle_error(self,
                            interaction: discord.Interaction,
                            error: discord.app_commands.AppCommandError):
        logger.error(error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(str(error), ephemeral=True)
            else:
                await interaction.response.send_message(str(error), ephemeral=True)
        except Exception:
            pass  # Avoid cascade errors


def read_git_head():
    if not os.path.isfile('.git/HEAD'):
        return None, None

    head = open('.git/HEAD').read().strip()

    if head.startswith('ref:'):
        ref = head.split(' ')[1]
        return head, open(f'.git/{ref}').read().strip()
    else:
        # Detached HEAD contains the hash directly
        return head, None


# --- Main Execution ---
logger.info(f'Starting Discord Bot... {read_git_head()}')

bot = HotReloadBot()
bot.run(DISCORD_TOKEN)
