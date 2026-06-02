"""
Temp script for testing ModalManager operations.
Requires MODAL_TOKEN_ID and MODAL_TOKEN_SECRET to be set in .env.
"""
import os
import sys

from dotenv import load_dotenv

from cogs.agent_elmo.modal_manager import ExecResult, ModalManager

# Load .env file
load_dotenv()

# Add Python directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_modal() -> bool:
    print("Testing ModalManager operations...")

    # Initialize ModalManager (will crash if Modal credentials missing)
    try:
        manager = ModalManager()
        print("[OK] ModalManager initialized")
    except Exception as e:
        print(f"[FAIL] Failed to initialize ModalManager: {e}")
        return False

    # Test 1: Ensure sandbox
    print("\nTest 1: Ensuring sandbox...")
    try:
        sandbox = manager.ensure_sandbox(channel_id=999)
        print(f"[OK] Sandbox created: {sandbox}")
    except Exception as e:
        print(f"[FAIL] Error creating sandbox: {e}")
        return False

    # Test 2: Execute a simple command
    print("\nTest 2: Executing command...")
    try:
        result = manager.exec_command("echo 'Hello from Modal'", channel_id=999)
        if isinstance(result, ExecResult):
            print(f"[OK] Command executed: exit_code={result.exit_code}, output={result.output}")
        else:
            print(f"[FAIL] Unexpected result type: {type(result)}")
            return False
    except Exception as e:
        print(f"[FAIL] Error executing command: {e}")
        return False

    # Test 3: Write and read a file
    print("\nTest 3: Writing file...")
    try:
        write_result = manager.write_file("/workspace/test.txt", "Hello Modal!", channel_id=999)
        print(f"[OK] File written: {write_result}")
    except Exception as e:
        print(f"[FAIL] Error writing file: {e}")
        return False

    print("\nTest 4: Reading file...")
    try:
        content = manager.read_file("/workspace/test.txt", channel_id=999)
        print(f"[OK] File read: {content}")
    except Exception as e:
        print(f"[FAIL] Error reading file: {e}")
        return False

    # Test 5: List directory
    print("\nTest 5: Listing directory...")
    try:
        listing = manager.list_dir("/workspace", channel_id=999)
        print(f"[OK] Directory listing:\n{listing}")
    except Exception as e:
        print(f"[FAIL] Error listing directory: {e}")
        return False

    # Cleanup
    print("\nCleaning up...")
    try:
        manager.stop(channel_id=999)
        print("[OK] Sandbox stopped")
    except Exception as e:
        print(f"[WARN] Error stopping sandbox: {e}")

    print("\n[OK] All ModalManager tests passed!")
    return True

if __name__ == "__main__":
    success = test_modal()
    sys.exit(0 if success else 1)
