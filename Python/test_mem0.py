"""
Temp script for testing mem0 read/write operations.
Requires MEM0_API_KEY to be set in environment.
"""
import os
import sys

from dotenv import load_dotenv
from mem0 import MemoryClient

# Load .env file
load_dotenv()

# Add Python directory to path
sys.path.insert(0, os.path.dirname(__file__))


def test_mem0():
    print("Testing mem0 read/write operations...")

    # Initialize client (will crash if MEM0_API_KEY is missing)
    client = MemoryClient(api_key=os.environ["MEM0_API_KEY"])
    print("[OK] MemoryClient initialized")

    # Test 1: Add a simple memory
    print("\nTest 1: Adding a memory...")
    try:
        # Try passing user_id as kwarg (not in filters)
        result = client.add("This is a test memory from temp script", user_id="test_user_123")
        print(f"[OK] Memory added: {result}")
    except Exception as e:
        print(f"[FAIL] Error adding memory: {e}")
        return False

    # Test 2: Search for the memory
    print("\nTest 2: Searching for memory...")
    try:
        # search() requires user_id inside filters dict
        results = client.search("test memory", filters={"user_id": "test_user_123"})
        # Convert generator to list
        results_list = list(results)
        if results_list:
            print(f"[OK] Found {len(results_list)} memory(s):")
            for r in results_list[:3]:  # Show first 3
                print(f"  - {r}")
        else:
            print("[FAIL] No memories found")
            return False
    except Exception as e:
        print(f"[FAIL] Error searching: {e}")
        return False

    # Test 3: Add structured conversation
    print("\nTest 3: Adding conversation messages...")
    try:
        messages = [
            {"role": "user", "content": "What is the capital of France?"},
            {"role": "assistant", "content": "The capital of France is Paris."}
        ]
        # Pass user_id as kwarg for add()
        result = client.add(messages, user_id="test_user_123")
        print(f"[OK] Conversation saved: {result}")
    except Exception as e:
        print(f"[FAIL] Error saving conversation: {e}")
        return False

    print("\n[OK] All mem0 tests passed!")
    return True

if __name__ == "__main__":
    success = test_mem0()
    sys.exit(0 if success else 1)
