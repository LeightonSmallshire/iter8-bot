import json
import os
import logging
import cogs.utils.bot as bot_utils
# import cogs.utils.database as db_utils
import cogs.utils.log as log_utils
import discord
from discord.ext import commands

assert __name__ == "__main__", 'Must be run directly'

# --- Configuration ---
DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
COGS_DIR = "cogs"

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Bot-FastAPI-Integrator")

# file_handler.setLevel(logging.DEBUG)
# file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(logging.FileHandler('logs.log'))
logger.addHandler(log_utils.DatabaseHandler())


class HotReloadBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())

    async def on_ready(self):
        """Starts the FastAPI server once the bot is connected."""
        logger.info(f'Discord Bot logged in as {self.user} (ID: {self.user.id})')
        bot_utils.defer_message(self, bot_utils.Users.Leighton, 'Bot connected')

        # leaderboard = await bot_utils.get_timeout_data(server)
        # db_utils.init_database(leaderboard)

        await self.hot_reload_cogs()

    async def setup_hook(self):
        """Prepares the initial loading of cogs."""
        logger.info('--- Starting FastAPI Server Task ---')

    async def hot_reload_cogs(self):
        """Unloads, reloads, and reports the status of all cogs."""

        logger.info('--- Loading cogs ---')
        bot_utils.defer_message(self, bot_utils.Users.Leighton, 'Reloading cogs')

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
                    logger.info(f"Successfully reloaded cog: {cog_name}")
                else:
                    await self.load_extension(cog_name)
                    logger.info(f"Successfully loaded NEW cog: {cog_name}")
                reloaded_cogs.append(cog_name)
            except Exception as e:
                logger.error(f"Failed to reload/load cog {cog_name}: {e}")
                failed_cogs.append(f"{cog_name} ({e.__class__.__name__})")

        # 3. Check for removed cogs
        for ext_name in list(self.extensions.keys()):
            if ext_name.startswith(f'{COGS_DIR}.') and ext_name not in current_cogs:
                try:
                    await self.unload_extension(ext_name)
                    logger.info(f"Successfully unloaded REMOVED cog: {ext_name}")
                except Exception as e:
                    logger.error(f"Failed to unload removed cog {ext_name}: {e}")

        logger.info('Syncing...')
        self.tree.copy_global_to(guild=discord.Object(id=bot_utils.Guilds.Paradise))
        synced = await self.tree.sync(guild=discord.Object(id=bot_utils.Guilds.Paradise))
        logger.info(f'Synced: {synced}')

        status = {
            'status': 'Cogs reloaded successfully',
            'reloaded': reloaded_cogs,
            'failed': failed_cogs,
            'synced': [str(c) for c in synced]
        }
        bot_utils.defer_message(self, bot_utils.Users.Leighton, json.dumps(status))
        return status


# --- Main Execution ---
logger.setLevel(logging.DEBUG)
logger.info("Starting Discord Bot...")
bot = HotReloadBot()
bot.run(DISCORD_TOKEN)
