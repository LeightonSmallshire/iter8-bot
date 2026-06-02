import os
import subprocess
import threading
import time
from queue import Queue


def test_bot_startup():
    """
    Runs the bot as a subprocess for 15 seconds to verify that it starts
    without critical failures (specifically checking cog loading).
    """
    python_exe = os.sys.executable
    cwd = os.getcwd()
    if cwd.endswith("Python"):
        cmd = [python_exe, "-u", "main.py"]
        run_cwd = cwd
    else:
        cmd = [python_exe, "-u", "Python/main.py"]
        run_cwd = cwd

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        cwd=run_cwd
    )

    output_queue = Queue()

    def read_output():
        try:
            for line in iter(process.stdout.readline, ''):
                output_queue.put(line)
        except Exception:
            pass

    t = threading.Thread(target=read_output, daemon=True)
    t.start()

    try:
        # Wait for bot to initialize (15 seconds)
        time.sleep(15)
    finally:
        process.terminate()
        process.wait()

    full_output = ""
    while not output_queue.empty():
        full_output += output_queue.get()

    # Check for critical failures
    assert "Failed to reload/load cog cogs.elmo_cog" not in full_output, \
        f"elmo_cog failed to load!\n\nFull output:\n{full_output}"

    # Verify it actually tried to load cogs
    assert "Loading cogs" in full_output

