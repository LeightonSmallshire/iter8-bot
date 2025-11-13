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

# --- FastAPI Setup ---
app = FastAPI()


class AsyncTee:
    def __init__(self):
        self._queue = asyncio.Queue()
        self._closed = False

    def write(self, text: str):
        sys.stdout.write(text)
        if not self._closed:
            asyncio.create_task(self._queue.put(text))

    def flush(self):
        sys.stdout.flush()

    def isatty(self):
        return sys.stdout.isatty()

    async def stream(self):
        while not self._closed or not self._queue.empty():
            text = await self._queue.get()
            yield text

    def close(self):
        self._closed = True


class DiscordPrinter:
    def __init__(self):
        self._next_send = 0
        self._msg_id = None
        self._buffer = io.StringIO()

    def write(self, text):
        sys.stdout.write(text)
        self._buffer.write(text)

        now = time.time()
        if now > self._next_send:
            self._next_send = now + 2.0
            self._msg_id = send_split_messages(self._buffer, self._msg_id)

    def flush(self):
        sys.stdout.flush()
        send_split_messages(self._buffer, self._msg_id)
        self._buffer.flush()

    def isatty(self):
        return sys.stdout.isatty()


def send_split_messages(buffer: io.StringIO, last_message_id: int | None = None) -> int | None:
    message = buffer.getvalue()

    # Split & consume buffer when exceeding discord's size limit
    while len(message) > 1900:
        split_idx = message.rindex('\n', None, 1950)
        split_idx = max(split_idx, 1800)
        sub_message = buffer.read(split_idx)
        message = message[split_idx:]
        last_message_id = do_hook(sub_message, last_message_id)
    else:
        last_message_id = None

    return do_hook(buffer.getvalue(), last_message_id)


def do_hook(message: str, edit_message_id: int | None = None) -> int | None:
    # print('HOOK', message)
    try:
        suppress_notifications = 1 << 12
        payload = json.dumps({'content': message, 'flags': suppress_notifications})
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


async def easy_run(args, *, stdout):
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd='/app/Runner',
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    async for block in process.stdout:
        stdout.write(block.decode())
    return await process.wait()


async def restart(repo_commit: str | None = None, stdout=sys.stdout):
    try:
        print('--- Rebuilding worker and recreating container ---', file=stdout)
        message_suffix = f' ({repo_commit[:8]})' if repo_commit else ''
        # message_id = do_hook(f'Update started{message_suffix}')
        print(f'--- Updated started{message_suffix} ---', file=stdout)

        print('--- Image rebuild ---', file=stdout)
        return_code = await easy_run([
            'docker', 'build',
            '-t', IMAGE_NAME,
            '-f', DOCKERFILE_NAME,
            '--build-arg', f'REPO_URL={REPO_URL}',
            '--build-arg', f'REPO_BRANCH={REPO_BRANCH}',
            '/app/Runner'], stdout=stdout)
        assert return_code == 0, 'Docker build failed'

        print('--- Container kill ---', file=stdout)
        await easy_run(['docker', 'rm', '-f', CONTAINER_NAME], stdout=stdout)

        print('--- Container start ---', file=stdout)
        return_code = await easy_run([
            'docker', 'run', '-d',
            '--name', CONTAINER_NAME,
            '--restart', 'unless-stopped',
            '--read-only',
            '--env-file', '/app/Runner/.env',
            '-v', f'{VOLUME_NAME}:/app/data',
            IMAGE_NAME
        ], stdout=stdout)
        assert return_code == 0, 'Docker run failed'

        print('Worker rebuilt and restarted.', file=stdout)
        # do_hook(f'Worker rebuilt and restarted{message_suffix}', message_id)

    except BaseException as e:
        traceback.print_exception(e)
        traceback.print_exception(e, file=stdout)
    finally:
        stdout.flush()


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

    asyncio.create_task(restart(payload.get('after'), stdout=DiscordPrinter()))
    return fastapi.responses.StreamingResponse(content='Accepted', media_type="text/plain")


@app.get("/restart")
async def manual_restart():
    buf = AsyncTee()
    asyncio.create_task(restart("Manual", stdout=buf))
    return fastapi.responses.StreamingResponse(buf.stream(), media_type="text/plain")


asyncio.run(restart("Startup", stdout=sys.stdout))
uvicorn.run(app, host='0.0.0.0', port=8080)
