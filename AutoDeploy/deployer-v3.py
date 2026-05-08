import asyncio
import os
import hmac
import hashlib
import subprocess
import logfire
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException

# --- Configuration ---
WEBHOOK_SECRET = os.environ['WEBHOOK_SECRET']
LOGFIRE_TRIGGER_TOKEN = os.environ['LOGFIRE_TRIGGER_TOKEN']

REPO_URL = "https://github.com/LeightonSmallshire/iter8-bot.git"
REPO_DIR = "./repo"
REPO_BRANCH = 'main'
REPO_REF = f'refs/heads/{REPO_BRANCH}'

# Pinned fingerprints for Alice and Bob
TRUSTED_FINGERPRINTS = [
    "0000000000000000000000000000000000000000",
    "0000000000000000000000000000000000000000"
]

# Initialize Logfire
logfire.configure()

# Global Event to trigger the background worker
deployment_trigger = asyncio.Event()


@logfire.instrument
async def run_command(cmd: list[str], cwd: str = "."):
    """Runs a command, merges stderr into stdout, and streams output to logfire."""
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd
    )

    while True:
        line = await process.stdout.readline()
        if not line:
            break
        text = line.decode().strip()
        if text:
            logfire.info(f"[output] {text}")

    return_code = await process.wait()
    if return_code != 0:
        logfire.error(f"Command '{cmd[0]}' failed with exit code {return_code}")
        raise subprocess.CalledProcessError(return_code, cmd)
    return return_code


@logfire.instrument
async def verify_signature():
    """Verifies the commit signature against the whitelist of fingerprints."""
    process = await asyncio.create_subprocess_exec(
        "git", "-C", REPO_DIR, "verify-commit", f"origin/{REPO_BRANCH}", "--raw",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await process.communicate()
    status_output = stderr.decode()

    is_valid = any(f"VALIDSIG {fp}" in status_output for fp in TRUSTED_FINGERPRINTS)

    if not is_valid:
        logfire.error("GPG Verification Failed: No valid signature found.")
        logfire.debug(f"Raw GPG Status: {status_output}")
        raise PermissionError("Commit signature verification failed.")

    logfire.info("Commit signature verified against trusted whitelist.")


@logfire.instrument
async def perform_deployment():
    """The full deployment sequence."""
    if not os.path.exists(os.path.join(REPO_DIR, ".git")):
        logfire.info("Repository missing. Cloning...")
        await run_command(["git", "clone", "--recurse-submodules", REPO_URL, REPO_DIR])

    logfire.info("Fetching latest updates...")
    await run_command(["git", "-C", REPO_DIR, "remote", "set-url", "origin", REPO_URL])
    await run_command(["git", "-C", REPO_DIR, "fetch", "--all", "--recurse-submodules", "--tags"])

    await verify_signature()

    logfire.info("Updating worktree...")
    await run_command(["git", "-C", REPO_DIR, "reset", "--hard", f"origin/{REPO_BRANCH}"])
    await run_command(["git", "-C", REPO_DIR, "submodule", "update", "--init", "--recursive"])

    logfire.info("Restarting Docker services...")
    await run_command([
        "docker", "compose",
        "-f", os.path.join(REPO_DIR, "docker-compose.yml"),
        "--env-file", ".env",
        "up", "--build", "--always-recreate-deps", "--force-recreate", "-d"
    ])


async def deployment_worker():
    """Background task to process deployment requests."""
    logfire.info("Deployment worker active.")
    while True:
        await deployment_trigger.wait()
        deployment_trigger.clear()

        try:
            await perform_deployment()
            logfire.info("Deployment cycle completed successfully.")
        except Exception as e:
            logfire.exception("Deployment cycle failed", exc_info=e)

        await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logfire.info("Application starting up...")
    deployment_trigger.set()
    worker_task = asyncio.create_task(deployment_worker())
    yield
    logfire.info("Application shutting down...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        logfire.info("Worker task cancelled successfully.")

app = FastAPI(lifespan=lifespan)


@app.post('/trigger')
@logfire.instrument
async def manual_trigger(token: str):
    """Manual trigger endpoint for Logfire buttons."""
    if not token or not hmac.compare_digest(token, LOGFIRE_TRIGGER_TOKEN):
        logfire.warn("Unauthorized manual trigger attempt")
        raise HTTPException(status_code=403, detail="Invalid trigger token")

    logfire.info("Manual deployment triggered via Logfire/API")
    deployment_trigger.set()
    return {"status": "triggered"}


@app.post('/webhook')
@logfire.instrument
async def handle_webhook(request: Request):
    signature = request.headers.get('X-Hub-Signature-256')
    if not signature:
        raise HTTPException(status_code=403, detail="Missing signature")

    body = await request.body()
    expected = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(f"sha256={expected}", signature):
        logfire.warn("Unauthorized webhook attempt detected")
        raise HTTPException(status_code=403, detail="Invalid signature")

    event = request.headers.get('x-github-event', '').lower()
    if event != 'push':
        return {"status": "skipped", "reason": "Not a push event"}

    payload = await request.json()
    if payload.get('ref') != REPO_REF:
        return {"status": "skipped", "reason": f"Irrelevant branch: {payload.get('ref')}"}

    logfire.info(f"Deployment triggered by push to {REPO_BRANCH}")
    deployment_trigger.set()
    return {"status": "accepted"}


if __name__ == '__main__':
    logfire.instrument_fastapi(app)
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
