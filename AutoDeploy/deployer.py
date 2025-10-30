import time
import traceback
import os
import uvicorn
import subprocess
import fastapi
from fastapi import FastAPI
import http.client
import json

assert __name__ == '__main__', 'Must be run directly'

REPO_PATH = 'Runner/repo'
REPO_URL = 'https://github.com/LeightonSmallshire/iter8-bot'
REPO_REMOTE = 'origin'
REPO_BRANCH = 'main'

CONTAINER_NAME = 'iter8-runner'
IMAGE_NAME = 'iter8-runner'
VOLUME_NAME = 'iter8-bot-data'

# --- FastAPI Setup ---
app = FastAPI()


def do_hook(message: str):
    try:
        payload = json.dumps({'content': message})
        conn = http.client.HTTPSConnection('discord.com')
        conn.request(method='POST',
                     url='/api/webhooks/1416059591522783312/O7wVzYh9tMOFdrVxdUC4tm3fT5ppB_sqWzIccNT_zUuvVjkZqXxByJpfWMKejM6P2OIQ',
                     body=payload, headers={'Content-Type': 'application/json'})
        response = conn.getresponse()
        print(response.status)
        conn.close()
    except:
        traceback.print_exc()


def restart():
    print('Rebuilding worker image and recreating container...')
    do_hook('Restart requested')

    build_env = os.environ.copy()
    build_env['CACHE_BUST'] = str(time.time_ns())

    # print('Handling git')
    # if not os.path.isdir(REPO_PATH + '/.git'):
    #     subprocess.run(['git', 'clone', REPO_URL, REPO_PATH], cwd='/', check=True)
    # subprocess.run(['git', 'fetch'], cwd=REPO_PATH, check=True)
    # subprocess.run(['git', 'reset', '--hard', f'{REPO_REMOTE}/{REPO_BRANCH}'], cwd=REPO_PATH, check=True)

    print('Image rebuild')
    subprocess.run([
        'docker', 'build',
        '-t', IMAGE_NAME,
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
        '--env-file', '.env',
        '-v', f'{VOLUME_NAME}:/app/data',
        IMAGE_NAME
    ], check=True)

    print('Worker rebuilt and restarted.')
    do_hook('Worker rebuilt and restarted.')


@app.get('/restart')
@app.get('/webhook')
@app.post('/webhook')
def handle_webhook(request: fastapi.Request):
    # await verify_signature(request)
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
