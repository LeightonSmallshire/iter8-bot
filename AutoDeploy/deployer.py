import asyncio
import io
import sys
import threading
import time
import traceback
import os
from http.client import HTTPException
from typing import Any
import queue
import uvicorn
import subprocess
import fastapi
from fastapi import FastAPI, BackgroundTasks
import http.client
import json
import hmac
import hashlib

import singleton_runner

assert __name__ == '__main__', 'Must be run directly'

REPO_URL = 'github.com/LeightonSmallshire/iter8-bot'
REPO_BRANCH = 'main'
REPO_REF = f'refs/heads/{REPO_BRANCH}'

CONTAINER_NAME = 'iter8-runner'
IMAGE_NAME = 'iter8-runner'
VOLUME_NAME = 'iter8-bot-data'
DOCKERFILE_NAME = 'Dockerfile'
# DOCKERFILE_NAME = 'Dockerfile2'

WEBHOOK_SECRET = os.environ['WEBHOOK_SECRET']
DISCORD_WEBOOK_ID = os.environ['DISCORD_WEBOOK_ID']
DISCORD_WEBOOK_TOKEN = os.environ['DISCORD_WEBOOK_TOKEN']

# ---

assert os.system('./update.sh') == 0
RESTART_RUNNER = singleton_runner.SingletonBashRunner('./update.sh')

# --- FastAPI Setup ---
app = FastAPI()


class DiscordPrinter:
    def __init__(self):
        self._next_send = 0
        self._msg_id = None
        self._buffer = io.StringIO()

    def write(self, text):
        # sys.stdout.write(text)
        self._buffer.write(text)

        now = time.time()
        if now > self._next_send:
            self._next_send = now + 2.0
            self._msg_id = send_split_messages(self._buffer, self._msg_id)

    def flush(self):
        # sys.stdout.flush()
        send_split_messages(self._buffer, self._msg_id)
        self._buffer.flush()

    @staticmethod
    def isatty():
        return sys.stdout.isatty()


def send_split_messages(buffer: io.StringIO, last_message_id: int | None = None) -> int | None:
    buffer.seek(0)
    message = buffer.read()

    need_new_block = False
    while len(message) > 1900:
        split_idx = message.rfind('\n', 0, 1950)
        if split_idx == -1 or split_idx < 1800:
            split_idx = 1900

        sub_message = message[:split_idx]
        last_message_id = do_hook(sub_message, last_message_id)
        message = message[split_idx:]
        need_new_block = True

    if need_new_block:
        last_message_id = None

    buffer.seek(0)
    buffer.truncate(0)
    buffer.write(message)

    return do_hook(message, last_message_id)


def do_hook(message: str, edit_message_id: int | None = None) -> int | None:
    # print('HOOK', message)
    try:
        suppress_embeds = 1 << 2
        suppress_notifications = 1 << 12
        payload = json.dumps({'content': message, 'flags': suppress_embeds | suppress_notifications})
        conn = http.client.HTTPSConnection('discord.com')
        url = f'/api/webhooks/{DISCORD_WEBOOK_ID}/{DISCORD_WEBOOK_TOKEN}'
        if edit_message_id is None:
            conn.request(method='POST', url=f'{url}?wait=1',
                         body=payload, headers={'Content-Type': 'application/json'})
        else:
            conn.request(method='PATCH', url=f'{url}/messages/{edit_message_id}?wait=1',
                         body=payload, headers={'Content-Type': 'application/json'})
        response = conn.getresponse()

        response_payload: dict = json.loads(response.read())
        message_id = response_payload.get('id')
        conn.close()
        return message_id
    except BaseException as e:
        traceback.print_exception(e)
        return None


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -

@app.post('/webhook')
async def handle_webhook(request: fastapi.Request, background_tasks: BackgroundTasks):
    # Verify the webhook headers & hmac

    if 'X-Hub-Signature-256' not in request.headers:
        raise fastapi.HTTPException(status_code=403, detail="Signature is missing")

    payload_body = await request.body()
    calculated_signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"),
                                    msg=payload_body, digestmod=hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f'sha256={calculated_signature}', request.headers['X-Hub-Signature-256']):
        raise fastapi.HTTPException(status_code=403, detail="Signature is incorrect")

    if request.headers['x-github-event'].lower() != 'push':
        return fastapi.Response('Only care about push', 200)

    payload = json.loads(payload_body)
    if payload.get('ref') != REPO_REF:
        return fastapi.Response(f'Only care about {REPO_REF}', 200)

    async def background():
        printer = DiscordPrinter()
        async for block in await RESTART_RUNNER.run():
            printer.write(block)
        printer.flush()

    asyncio.create_task(background())
    return 'Accepted'


@app.get("/restart")
async def manual_restart():
    return fastapi.responses.StreamingResponse(await RESTART_RUNNER.run(), media_type="text/plain")


uvicorn.run(app, host='0.0.0.0', port=8080)
