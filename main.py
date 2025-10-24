import contextlib
import asyncio
import discord
import discord.ext.commands
import io
import os
import logging
import traceback
import fastapi
import sys
import json

from cogs.bot_utils import ID_GUILD_PARADISE

logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)

# # --- ADD THIS SECTION ---
# # Create a console handler
# handler = logging.StreamHandler(sys.stdout)
# handler.setLevel(logging.DEBUG)
#
# # Create a formatter and add it to the handler
# formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# handler.setFormatter(formatter)
#
# # Add the handler to the logger
# if not logger.handlers:  # Avoid adding duplicate handlers if the code is reloaded
#     logger.addHandler(handler)
# # ------------------------

# ---------- discord ----------

client = discord.ext.commands.Bot(command_prefix='!',
                                  intents=discord.Intents.all(),
                                  application_id=1425483577587531886)


@client.event
async def on_ready():
    """Executed when the bot is ready and connected to Discord."""
    logger.info('Syncing Commands...')
    paradise_guild = discord.utils.get(client.guilds, id=ID_GUILD_PARADISE)
    logger.info(f"Sync Done: {await client.tree.sync(guild=paradise_guild)}")


@client.event
async def on_error(event, *args, **kwargs):
    buf = io.StringIO()
    traceback.print_exc(file=buf)
    logger.error(f'An error occurred during event: {event} \n {buf.read()}')


async def run_bot():
    try:
        async with client:
            await client.start(os.getenv('DISCORD_TOKEN'))
    except KeyboardInterrupt:
        # todo; restart? what?
        return


# ---------- github ----------

@contextlib.asynccontextmanager
async def app_lifespan(_):
    logger.info('lifespan start')
    await do_update()  # update before start

    bot_task = asyncio.create_task(run_bot())
    yield  # app is running
    bot_task.cancel()
    logger.info('lifespan end')


app = fastapi.FastAPI(lifespan=app_lifespan)


@app.post('/webhook/github')
async def github_hook(req: fastapi.Request):
    payload: dict = await req.json()
    logger.debug(json.dumps(payload, indent=4), req.client.host)
    assert payload['config']['secret'] == os.getenv('WEBHOOK_SECRET'), 'Secret mismatch'


async def do_update():
    username = 'LeightonSmallshire'
    token = os.getenv('GITHUB_SECRET')
    repo_name = 'iter8-bot'
    repo_url = f'https://{username}:{token}@github.com/{username}/{repo_name}.git'

    # Repository exists: Use fetch + reset --hard for a clean update
    logger.debug(f"Updating 'master' in using fetch/reset...")

    original_cwd = os.getcwd()
    try:
        update_commands = [
            ['git', 'fetch', 'origin'],
            ['git', 'reset', '--hard', 'origin/master'],
            ['git', 'clean', '-fd']
        ]

        for cmd in update_commands:
            logger.debug(f"Executing: {cmd}")
            process = await asyncio.create_subprocess_exec(*cmd,
                                                           stdout=asyncio.subprocess.PIPE,
                                                           stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                logger.error(f"Git command failed: {cmd}")
                logger.error(stderr.decode().strip())
                return
            logger.debug(stdout.decode().strip())

        logger.info("Update complete.")

    finally:
        os.chdir(original_cwd)
