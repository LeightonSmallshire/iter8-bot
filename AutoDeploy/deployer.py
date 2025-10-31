import time
import traceback
import os
from http.client import HTTPException
from typing import Any

import uvicorn
import subprocess
import fastapi
from fastapi import FastAPI
import http.client
import json
import hmac
import hashlib

assert __name__ == '__main__', 'Must be run directly'

REPO_PATH = 'Runner/repo'
REPO_URL = 'https://github.com/LeightonSmallshire/iter8-bot'
REPO_REMOTE = 'origin'
REPO_BRANCH = 'main'
REPO_REF = f'refs/heads/{REPO_BRANCH}'

CONTAINER_NAME = 'iter8-runner'
IMAGE_NAME = 'iter8-runner'
VOLUME_NAME = 'iter8-bot-data'
DOCKERFILE_NAME = 'Dockerfile'
# DOCKERFILE_NAME = 'Dockerfile-distroless'

WEBHOOK_SECRET = os.environ['WEBHOOK_SECRET']
DISCORD_WEBOOK_ID = os.environ['DISCORD_WEBOOK_ID']
DISCORD_WEBOOK_TOKEN = os.environ['DISCORD_WEBOOK_TOKEN']

# --- FastAPI Setup ---
app = FastAPI()


def do_hook(message: str, edit_message_id: int | None = None) -> int | None:
    try:
        suppress_notifications = 1 << 12
        payload = json.dumps({'content': message, 'flags': suppress_notifications})
        conn = http.client.HTTPSConnection('discord.com')
        url = f'/api/webhooks/{DISCORD_WEBOOK_ID}/{DISCORD_WEBOOK_TOKEN}'
        if edit_message_id is not None:
            url = f'{url}/messages/{edit_message_id}'
        conn.request(method='POST', url=f'{url}?wait=1', body=payload, headers={'Content-Type': 'application/json'})
        response = conn.getresponse()

        response_payload: dict = json.loads(response.read())
        message_id = response_payload['id']
        conn.close()
        return message_id
    except:
        traceback.print_exc()
        return None


def restart(repo_commit: str | None = None):
    print('Rebuilding worker image and recreating container...')
    message_id = do_hook(f'Restart requested ({repo_commit})')

    build_env = os.environ.copy()
    build_env['CACHE_BUST'] = str(time.time_ns())
    # build_env['COMMIT_HASH'] = repo_commit

    print('Image rebuild')
    subprocess.run([
        'docker', 'build',
        '-t', IMAGE_NAME,
        '-f', DOCKERFILE_NAME,
        '.',
    ], check=True, cwd='/app/Runner', env=build_env)

    print('Container kill')
    subprocess.run(['docker', 'rm', '-f', CONTAINER_NAME], check=False)

    print('Container start')
    subprocess.run([
        'docker', 'run', '-d',
        '--name', CONTAINER_NAME,
        '--restart', 'unless-stopped',
        '--read-only',
        '--env-file', 'Runner/.env',
        '-v', f'{VOLUME_NAME}:/app/data',
        IMAGE_NAME
    ], check=True)

    print('Worker rebuilt and restarted.')
    do_hook(f'Worker rebuilt and restarted. ({repo_commit})', message_id)


@app.post('/webhook')
async def handle_webhook(request: fastapi.Request):
    # Verify the webhook headers & hmac

    if 'X-Hub-Signature-256' not in request.headers:
        raise fastapi.HTTPException(status_code=403, detail="x-hub-signature-256 header is missing")

    payload_body = await request.body()
    calculated_signature = f'sha256={hmac.new(WEBHOOK_SECRET.encode('utf-8'),
                                              msg=payload_body, digestmod=hashlib.sha256).hexdigest()}'
    if not hmac.compare_digest(calculated_signature, request.headers['X-Hub-Signature-256']):
        raise fastapi.HTTPException(status_code=403, detail="x-hub-signature-256 header is incorrect")

    # Filtering only events we want

    if request.headers['x-github-event'].lower() != 'push':
        return fastapi.Response('Only care about push', 200)

    payload = json.loads(payload_body)
    if payload.get('ref') != REPO_REF:
        return fastapi.Response(f'Only care about {REPO_REF}', 200)

    latest_commit = payload.get('after')

    try:
        restart(latest_commit)
        return fastapi.Response('Accepted', 202)
    except BaseException as e:
        lines = traceback.format_exception(e)
        return fastapi.Response(''.join(lines), 500)


@app.get('/restart')
def manual_restart():
    try:
        restart()
        return fastapi.Response('Accepted', 202)
    except BaseException as e:
        lines = traceback.format_exception(e)
        return fastapi.Response(''.join(lines), 500)


try:
    restart()
except BaseException as e:
    traceback.print_exc()
    time.sleep(10)

uvicorn.run(app, host='0.0.0.0', port=8080)
