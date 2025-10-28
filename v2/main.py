import uvicorn
import os
import subprocess
import logging
import fastapi
import shutil
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
        logger.info("killing bot")
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()

    #
    username = 'LeightonSmallshire'
    repo_name = 'iter8-bot'
    branch = 'main-v2'
    # url = f'https://{username}:{GITHUB_SECRET}@github.com/{username}/{repo_name}/archive/refs/heads/{branch}.tar.gz'
    url = f'https://github.com/{username}/{repo_name}/archive/refs/heads/{branch}.tar.gz'

    logger.info("removing old dir")

    if os.path.exists(BOT_DIR):
        subprocess.run(['rm', '-rf', BOT_DIR], cwd='/', check=False)

    logger.info("making empty dir")

    # todo shutil rmtree
    os.makedirs(BOT_DIR, exist_ok=True)

    logger.info("wget | tar")

    # Start the wget process and pipe its output to tar
    with subprocess.Popen(["wget", "-qO-", url], stdout=subprocess.PIPE, cwd=BOT_DIR) as wget_process:
        with subprocess.Popen(["tar", "-xz"], stdin=wget_process.stdout, cwd=BOT_DIR) as tar_process:
            a, b = tar_process.communicate()
            # wget_process.stdout.close()  # Allow wget to receive a SIGPIPE if tar exits

    logger.info(a)
    logger.info(b)
    logger.info(wget_process.returncode)
    logger.info(tar_process.returncode)

    logger.info("starting bot")
    bot_process = subprocess.Popen(['python3', 'iter8-bot-main-v2/bot-main.py'], cwd=BOT_DIR)


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

# try:
#     restart()
# except BaseException as e:
#     logger.error(repr(e))

# uvicorn.run(app, host='0.0.0.0', port=8090)
