import uvicorn
import os
import subprocess

import fastapi
from fastapi import FastAPI

assert __name__ == "__main__", 'Must be run directly'

# --- Configuration ---
GITHUB_SECRET = os.environ.get("GITHUB_SECRET")
BOT_DIR = './bot_dir'

log_file = open('deploy_log.txt', 'a')

# --- FastAPI Setup ---
app = FastAPI()

bot_process: None | subprocess.Popen = None


def restart():
    global bot_process
    if bot_process is not None:
        bot_process.terminate()
        try:
            bot_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            bot_process.kill()

    #
    username = 'LeightonSmallshire'
    password = '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'
    url = f'https://{username}:{password}@github.com/LeightonSmallshire/iter8-bot/archive/refs/heads/main-v2.zip'

    subprocess.run(['rm', '-rf', BOT_DIR], cwd='/', check=True)

    # Start the wget process and pipe its output to tar
    with subprocess.Popen(["wget", "-qO-", url], stdout=subprocess.PIPE, cwd=BOT_DIR) as wget_process:
        with subprocess.Popen(["tar", "-xz"], stdin=wget_process.stdout, cwd=BOT_DIR) as tar_process:
            wget_process.stdout.close()  # Allow wget to receive a SIGPIPE if tar exits
            tar_process.communicate()

    bot_process = subprocess.Popen(['python3', 'main.py'], cwd=BOT_DIR)


@app.post('/webhook')
def handle_webhook(request: fastapi.Request):
    # await verify_signature(request)
    print("POST request received at /webhook. Initiating git pull and cog reload.", file=log_file)
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


try:
    restart()
except BaseException as e:
    print(repr(e), file=log_file)

uvicorn.run(app, host='0.0.0.0', port=8090)
