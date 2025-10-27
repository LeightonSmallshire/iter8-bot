import hashlib
import hmac
import os
import sys
import subprocess
import asyncio
import logging
from typing import List

import fastapi
import uvicorn
from fastapi import FastAPI, HTTPException
import discord
from discord.ext import commands

assert __name__ == "__main__", 'Must be run directly'

# --- Configuration ---
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET")
GITHUB_SECRET = os.environ.get("GITHUB_SECRET")

# The directory containing your Discord cogs (Python files)
COGS_DIR = "cogs"

# Webhook host/port configuration
WEBHOOK_HOST = "0.0.0.0"
WEBHOOK_PORT = 8080

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Bot-FastAPI-Integrator")


# --- Discord Bot Setup ---


async def run_blocking_command(cmd: List[str], cwd: str = '.') -> str:
    """Runs a blocking subprocess command in a separate thread."""
    logger.info(f"Executing command: {' '.join(cmd)} in directory: {cwd}")

    def blocking_call():
        # Run the synchronous subprocess call
        return subprocess.run(
            cmd,
            cwd=cwd,
            check=True,  # Raise exception on non-zero exit code
            capture_output=True,
            text=True,
            timeout=30  # Prevent indefinite hang
        )

    try:
        # Execute the blocking call in a separate thread to not block the event loop
        result = await asyncio.to_thread(blocking_call)
        logger.info(f"Command successful. Output: {result.stdout.strip()}")
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed (exit code {e.returncode}): {e.stderr.strip()}")
        raise HTTPException(status_code=500, detail=f"Git operation failed: {e.stderr.strip()}")
    except subprocess.TimeoutExpired:
        logger.error("Command timed out.")
        raise HTTPException(status_code=500, detail="Git operation timed out.")
    except Exception as e:
        logger.error(f"An unexpected error occurred during command execution: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


async def git_pull_and_reset():
    """Performs git pull and hard reset on the cogs directory."""
    origin_url = f'https://LeightonSmallshire:{GITHUB_SECRET}@github.com/LeightonSmallshire/iter8-bot'

    if not os.path.exists('.git'):
        logger.error('NOT A GIT REPO - bad - explode - die horribly')
        exit(-1)
        # await run_blocking_command(['git', 'remote', 'set-url', 'origin', origin_url])
    else:
        await run_blocking_command(['git', 'remote', 'set-url', 'origin', origin_url])

    await run_blocking_command(['git', 'fetch', 'origin', 'main'])
    await run_blocking_command(['git', 'reset', '--hard', 'origin/main'])
    logger.info("Git pull and hard reset complete.")


class HotReloadBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self._fastapi_task = None

    async def on_ready(self):
        """Starts the FastAPI server once the bot is connected."""
        logger.info(f'Discord Bot logged in as {self.user} (ID: {self.user.id})')

        try:
            await git_pull_and_reset()
        except BaseException as e:
            logger.error(f'{e}')

        await self.hot_reload_cogs()

    async def setup_hook(self):
        """Prepares the initial loading of cogs."""
        logger.info('--- Starting FastAPI Server Task ---')

        # Uvicorn configuration setup
        # Use an absolute import path for the app if possible, but here we pass the object directly
        config = uvicorn.Config(
            app,
            host=WEBHOOK_HOST,
            port=WEBHOOK_PORT,
            log_level="info",
            # We must instruct uvicorn to run its server in the bot's existing event loop
            loop="asyncio",
            workers=1  # Essential: Run in single process/thread to share global state
        )

        # Initialize Uvicorn Server
        server = uvicorn.Server(config)

        # Start the Uvicorn server as a non-blocking background task in the bot's event loop
        self._fastapi_task = self.loop.create_task(server.serve())

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

        logger.info('syncing...')
        self.tree.copy_global_to(guild=discord.Object(id=1416007094339113071))
        logger.info(f'Synced: {await self.tree.sync(guild=discord.Object(id=1416007094339113071))}')

        return {
            "status": "Cogs reloaded successfully",
            "reloaded": reloaded_cogs,
            "failed": failed_cogs
        }


# --- FastAPI Setup ---
# The FastAPI app instance
app = FastAPI(title="Discord Bot Webhook Handler")

# Initialize the bot (must happen before main execution)
# Note: The bot instance is global so the FastAPI route can access it.
bot = HotReloadBot()


async def verify_signature(request: fastapi.Request):
    """Verify that the payload was sent from GitHub by validating SHA256"""
    if 'X-Hub-Signature-256' not in request.headers:
        raise HTTPException(status_code=403, detail="X-Hub-Signature-256 header is missing")

    hash_object = hmac.new(WEBHOOK_SECRET.encode('utf-8'), msg=await request.body(), digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, request.headers['X-Hub-Signature-256']):
        raise HTTPException(status_code=403, detail="HMAC mismatch")


@app.post("/webhook")
async def handle_webhook(request: fastapi.Request, response: fastapi.Response):
    """
    Endpoint to trigger a git pull and hot-reload of all Discord cogs.
    This needs to respond within 10s... too lazy for now
    """
    await verify_signature(request)
    logger.info("POST request received at /webhook. Initiating git pull and cog reload.")

    # 1. Perform Git operations
    try:
        await git_pull_and_reset()
    except BaseException as e:
        logger.error(f'{e}')

    # 2. Perform hot reload
    await bot.hot_reload_cogs()
    return fastapi.Response('Accepted', 202)


@app.get("/status")
def get_status():
    """Simple health check endpoint."""
    return {
        "bot_status": "Ready" if bot._fastapi_task is not None else "Connecting",
        "cogs_loaded": list(bot.extensions.keys()),
        "webhook_endpoint": f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook"
    }


logger.setLevel(logging.DEBUG)

# --- Main Execution ---
try:
    logger.info("Starting Discord Bot...")
    # The bot.run() method is blocking and starts the main event loop.
    # The FastAPI server will be started as a task within the bot
    bot.run(DISCORD_TOKEN)
except discord.LoginFailure:
    logger.error("Discord login failed. Check your bot token.")
    sys.exit(1)
except KeyboardInterrupt:
    logger.info("Shutting down...")
    if bot._fastapi_task:
        bot._fastapi_task.cancel()  # Cancel the uvicorn server task
    # The bot's loop will automatically stop
    sys.exit(0)
except Exception as e:
    logger.error(f"An unexpected error occurred during runtime: {e}")
    sys.exit(1)
