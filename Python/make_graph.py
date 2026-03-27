import os
import subprocess
import json
import sys

os.chdir(os.path.dirname(__file__))

def generate_mermaid():
    try:
        # Run ruff analyze graph and capture the JSON output
        result = subprocess.run(
            ["python", "-m", "ruff", "analyze", "graph"],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Parse the JSON data
        data = json.loads(result.stdout)
        
        if not data:
            print("No data found. Ensure you are running this in a Python project.")
            return

        # Start building the Mermaid string with an explicit initial newline
        mermaid_lines = ["graph TD"]
        
        for node, edges in data.items():
            # Clean up: Replace backslashes with forward slashes for Mermaid compatibility
            safe_node = node.replace("\\", "/")
            source = f'{safe_node}'
            
            for edge in edges:
                safe_edge = edge.replace("\\", "/")
                target = f'{safe_edge}'
                mermaid_lines.append(f'    {source} --> {target}')
        
        # Combine with clear newlines
        mermaid_output = "\n".join(mermaid_lines)
        print("\n--- Generated Mermaid Diagram ---\n")
        print(mermaid_output)
        print("\n----------------------------------")

    except subprocess.CalledProcessError as e:
        print(f"Error running ruff: {e.stderr}", file=sys.stderr)
    except FileNotFoundError:
        print("Error: 'ruff' is not installed or not in your PATH.", file=sys.stderr)
    except json.JSONDecodeError:
        print("Error: Failed to parse JSON output from ruff.", file=sys.stderr)


if __name__ == "__main__":
    generate_mermaid()
