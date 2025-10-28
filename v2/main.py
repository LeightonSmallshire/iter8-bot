import uvicorn
import os
import subprocess
import logging
import fastapi
from fastapi import FastAPI

assert __name__ == "__main__", 'Must be run directly'

# apt update && apt install -y wget procps git tar

# --- Configuration ---
GITHUB_SECRET = os.environ.get("GITHUB_SECRET")
BOT_DIR = '/bot_dir'

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoUpdater")

file_handler = logging.FileHandler('/update-logs.log')
logger.setLevel(logging.DEBUG)
logger.addHandler(file_handler)

# --- FastAPI Setup ---
app = FastAPI()

bot_process: None | subprocess.Popen = None


def restart():
    global bot_process

    logger.info("Doing autoupdate")

    if bot_process is not None:
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()

    #
    username = 'LeightonSmallshire'
    url = f'https://{username}:{GITHUB_SECRET}@github.com/LeightonSmallshire/iter8-bot/archive/refs/heads/main-v2.zip'

    if os.path.exists(BOT_DIR):
        subprocess.run(['rm', '-rf', BOT_DIR], cwd='/', check=False)

    # Start the wget process and pipe its output to tar
    with subprocess.Popen(["wget", "-qO-", url], stdout=subprocess.PIPE, cwd=BOT_DIR) as wget_process:
        with subprocess.Popen(["tar", "-xz"], stdin=wget_process.stdout, cwd=BOT_DIR) as tar_process:
            wget_process.stdout.close()  # Allow wget to receive a SIGPIPE if tar exits
            tar_process.communicate()

    bot_process = subprocess.Popen(['python3', 'bot-main.py'], cmd=BOT_DIR)


@app.post('/webhook')
def handle_webhook(request: fastapi.Request):
    # await verify_signature(request)
    restart()
    return fastapi.Response('Accepted', 202)


@app.get('/restart')
def handle_webhook():
    restart()


@app.get("/status")
def get_status():
    """Simple health check endpoint."""
    return {
        # "bot_status": "Ready" if bot._fastapi_task is not None else "Connecting",
        # "cogs_loaded": list(bot.extensions.keys()),
        # "webhook_endpoint": f"http://{WEBHOOK_HOST}:{WEBHOOK_PORT}/webhook"
    }


restart()
exit(0)

try:
    restart()
except BaseException as e:
    logger.error(repr(e))

uvicorn.run(app, host='0.0.0.0', port=8090)
