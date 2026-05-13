import os
import subprocess
import sys

# Define temp directory
TEMP_DIR = os.path.join(os.getcwd(), "temp")
if not os.path.exists(TEMP_DIR):
    os.makedirs(TEMP_DIR)

# Define commands. Working directory is the project root, but we run in Python directory.
WORKING_DIR = os.path.join(os.getcwd(), "Python")
    
cmds = {
    "mypy": [sys.executable, "-m", "mypy", "--show-error-codes", "--strict", "."],
    "ruff": [sys.executable, "-m", "ruff", "check", "."],
    "pytest": [sys.executable, "-m", "pytest", "--tb=short"]
}

for name, cmd in cmds.items():
    output_path = os.path.join(TEMP_DIR, f"{name}_results.txt")
    print(f"Running {name}, output: {output_path}")
    
    # Run in the Python directory
    result = subprocess.run(cmd, cwd=WORKING_DIR, capture_output=True, text=True)
    
    with open(output_path, "w") as f:
        f.write(result.stdout)
        f.write(result.stderr)
        
print("All tests completed.")
