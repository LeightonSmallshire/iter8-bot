import asyncio
import hashlib
import hmac
import json
import os
import time
import dotenv
from typing import Optional, List
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, StreamingResponse

dotenv.load_dotenv()

# --- Configuration ---
REPO_BRANCH = os.getenv('REPO_BRANCH', 'main')
REPO_REF = f'refs/heads/{REPO_BRANCH}'
GITHUB_WEBHOOK_SECRET = os.environ['GITHUB_WEBHOOK_SECRET']
UPDATE_SCRIPT = "./update.sh"

app = FastAPI(title="Iter8 Bot Dashboard")

SIGTERM = 15


# --- Process Management (Singleton Runner) ---


class UpdateRunner:
    def __init__(self):
        self.process: Optional[asyncio.subprocess.Process] = None
        self.logs: List[str] = ["[System] Waiting for initial run..."]
        self.start_time: Optional[float] = None
        self.new_log_event = asyncio.Event()

    async def add_log(self, text: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{timestamp}] {text}"
        self.logs.append(formatted)
        # Keep only last 10000 lines
        if len(self.logs) > 10000:
            self.logs.pop(0)
        self.new_log_event.set()
        self.new_log_event.clear()

    async def run(self):
        if self.process is not None:
            await self.add_log("Attempted to start runner but it's already active.")
            return

        self.start_time = time.time()
        self.logs = []  # Clear logs for new run
        await self.add_log(f"Starting {UPDATE_SCRIPT}...")

        try:
            self.process = await asyncio.create_subprocess_exec(
                UPDATE_SCRIPT,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True
            )

            # noinspection PyTypeChecker
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    break
                await self.add_log(line.decode().strip())

            await self.process.wait()
            await self.add_log(f"Process finished with exit code {self.process.returncode}")
        except Exception as e:
            await self.add_log(f"Runner Error: {str(e)}")
        finally:
            self.process = None

    async def interrupt(self):
        if self.process is None:
            return "Not running."

        await self.add_log("Sending SIGTERM...")
        os.killpg(os.getpgid(self.process.pid), SIGTERM)

        # Wait a bit for graceful exit, then kill if necessary
        try:
            await asyncio.wait_for(self.process.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            await self.add_log("Process didn't stop. Sending SIGKILL...")
            self.process.kill()

        return f"Interrupt signal sent. Exited with code {self.process.returncode}"


runner = UpdateRunner()


# --- Webhook Verification ---

def verify_signature(payload_body: bytes, signature_header: str):
    if not signature_header:
        raise HTTPException(status_code=403, detail="Signature missing")

    hash_object = hmac.new(GITHUB_WEBHOOK_SECRET.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=403, detail="Invalid signature")


# --- Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def index():
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Iter8 Bot Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .terminal {{
                background-color: #1a1a1a;
                color: #00ff00;
                font-family: 'Courier New', Courier, monospace;
                height: 500px;
                overflow-y: auto;
                padding: 1rem;
                border-radius: 0.5rem;
            }}
        </style>
    </head>
    <body class="bg-gray-900 text-gray-100 min-h-screen p-4 md:p-8">
        <div class="max-w-4xl mx-auto">
            <header class="flex flex-col md:flex-row justify-between items-center mb-8 gap-4">
                <div>
                    <h1 class="text-3xl font-bold text-white">Iter8 Dashboard</h1>
                    <p class="text-gray-400">Target: {REPO_REF}</p>
                </div>
                <div class="flex gap-2">
                    <button id="runBtn" onclick="triggerUpdate()" class="bg-green-600 hover:bg-green-700 text-white px-6 py-2 rounded-lg font-medium transition">
                        Run Update
                    </button>
                    <button id="stopBtn" onclick="triggerInterrupt()" class="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg font-medium transition">
                        Interrupt
                    </button>
                </div>
            </header>

            <div class="bg-gray-800 rounded-xl shadow-2xl p-6 mb-6">
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-xl font-semibold">Live Logs</h2>
                    <span id="status" class="px-3 py-1 rounded-full text-xs font-bold uppercase">Idle</span>
                </div>
                <div id="terminal" class="terminal text-sm"></div>
            </div>

            <footer class="text-center text-gray-500 text-sm">
                Iter8 Bot Runner &copy; {datetime.now().year}
            </footer>
        </div>

        <script>
            const terminal = document.getElementById('terminal');
            const statusLabel = document.getElementById('status');
            const runBtn = document.getElementById('runBtn');

            function updateStatus(running) {{
                if (running) {{
                    statusLabel.innerText = 'Running';
                    statusLabel.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase bg-green-900 text-green-200';
                    runBtn.disabled = true;
                    runBtn.classList.add('opacity-50', 'cursor-not-allowed');
                }} else {{
                    statusLabel.innerText = 'Idle';
                    statusLabel.className = 'px-3 py-1 rounded-full text-xs font-bold uppercase bg-gray-700 text-gray-300';
                    runBtn.disabled = false;
                    runBtn.classList.remove('opacity-50', 'cursor-not-allowed');
                }}
            }}

            async function triggerUpdate() {{
                const res = await fetch('/restart', {{ method: 'POST' }});
                const data = await res.json();
                appendLog('[UI] ' + data.message);
            }}

            async function triggerInterrupt() {{
                const res = await fetch('/interrupt', {{ method: 'POST' }});
                const data = await res.json();
                appendLog('[UI] ' + data.message);
            }}

            function appendLog(text) {{
                const div = document.createElement('div');
                div.textContent = text;
                terminal.appendChild(div);
                terminal.scrollTop = terminal.scrollHeight;
            }}

            // Start SSE Stream
            const evtSource = new EventSource("/logs/stream");
            evtSource.onmessage = function(event) {{
                const data = JSON.parse(event.data);

                // If it's the initial batch of logs
                if (Array.isArray(data.logs)) {{
                    terminal.innerHTML = '';
                    data.logs.forEach(log => appendLog(log));
                }} else if (data.log) {{
                    appendLog(data.log);
                }}

                updateStatus(data.is_running);
            }};

            evtSource.onerror = function() {{
                console.error("SSE Connection lost.");
                statusLabel.innerText = "Connection Lost";
                statusLabel.className = "px-3 py-1 rounded-full text-xs font-bold uppercase bg-red-900 text-red-200";
            }};
        </script>
    </body>
    </html>
    """


@app.post("/restart")
async def manual_restart(background_tasks: BackgroundTasks):
    if runner.process is not None:
        return {"message": "Already running"}
    background_tasks.add_task(runner.run)
    return {"message": "Update script triggered"}


@app.post("/interrupt")
async def manual_interrupt():
    msg = await runner.interrupt()
    return {"message": msg}


@app.get("/logs/stream")
async def stream_logs():
    async def log_generator():
        # First, send existing logs
        yield f"data: {json.dumps({'logs': runner.logs, 'is_running': runner.process is not None})}\n\n"

        while True:
            await runner.new_log_event.wait()
            if runner.logs:
                latest_log = runner.logs[-1]
                yield f"data: {json.dumps({'log': latest_log, 'is_running': runner.process is not None})}\n\n"

    return StreamingResponse(log_generator(), media_type="text/event-stream")


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    signature = request.headers.get("X-Hub-Signature-256")
    body = await request.body()
    verify_signature(body, signature)

    event = request.headers.get("X-GitHub-Event", "ping")
    if event.lower() == "ping":
        return {"message": "pong"}

    if event.lower() != "push":
        return {"message": "Ignored event"}

    payload = json.loads(body)
    if payload.get("ref") != REPO_REF:
        return {"message": f"Ignoring ref {payload.get('ref')}"}

    if not runner.process is not None:
        background_tasks.add_task(runner.run)
        return {"status": "Accepted", "action": "Running update script"}
    else:
        return {"status": "Accepted", "action": "Runner already active"}


if __name__ == "__main__":
    # Ensure the update script exists and is executable
    if not os.path.exists(UPDATE_SCRIPT):
        with open(UPDATE_SCRIPT, "w") as f:
            f.write(
                "#!/bin/bash\necho 'Default update script created.'\necho 'Running git pull...'\nsleep 2\necho 'Build complete.'")
        os.chmod(UPDATE_SCRIPT, 0o755)

    print(f"Starting Iter8 Dashboard on port 8080...")
    uvicorn.run(app, host="0.0.0.0", port=8080)
