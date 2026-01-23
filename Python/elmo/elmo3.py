import json
from typing import Dict, Any, List
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from llama_cpp.llama_grammar import LlamaGrammar

# 1. SETUP: Download and Load Model
print("Downloading model... this may take a moment.")
model_path = hf_hub_download(
    repo_id="MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
    filename="Mistral-7B-Instruct-v0.3.Q4_K_M.gguf"
)

# Initialize the Llama object directly for fine-grained grammar control
llm = Llama(
    model_path=model_path,
    n_ctx=2048,
    n_gpu_layers=-1,
    verbose=False
)

# 2. DEFINE THE SCHEMA (Grammar)
# This schema forces the model to choose one of three tools.
TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "tool_name": {
            "enum": ["python_repl", "web_search", "respond_to_user"]
        },
        "tool_input": {"type": "string"}
    },
    "required": ["tool_name", "tool_input"]
}

# Convert schema to GBNF grammar
grammar = LlamaGrammar.from_json_schema(json.dumps(TOOL_SCHEMA))

# 3. DEFINE THE ACTUAL TOOL FUNCTIONS


def python_repl(code: str) -> str:
    print(f"--- Executing Python ---\n{code}")
    try:
        # Simple local execution environment
        local_vars = {}
        exec(code, {}, local_vars)
        return str(local_vars)
    except Exception as e:
        return f"Error: {str(e)}"


def web_search(query: str) -> str:
    print(f"--- Searching Web: {query} ---")
    # For a full implementation, use: from langchain_community.tools import DuckDuckGoSearchRun
    return f"Search result for '{query}': The current date is early 2026, and Bitcoin is trading at $150,000."

# 4. THE AGENT LOOP


def run_agent(user_prompt: str):
    messages = [
        {"role": "system", "content": "You are a helpful assistant. You MUST use a tool for every response. Use 'respond_to_user' to give your final answer."},
        {"role": "user", "content": user_prompt}
    ]

    while True:
        # Format the prompt for Mistral
        prompt = ""
        for msg in messages:
            prompt += f"[{msg['role']}]\n{msg['content']}\n"
        prompt += "[assistant]\n"

        # Generate output constrained by grammar
        output = llm(
            prompt,
            grammar=grammar,
            max_tokens=500,
            stop=["[/assistant]"]
        )

        # Parse the JSON output (Guaranteed to be valid by the grammar)
        action = json.loads(output["choices"][0]["text"])
        tool_name = action["tool_name"]
        tool_input = action["tool_input"]

        if tool_name == "respond_to_user":
            print(f"\nFINAL RESPONSE: {tool_input}")
            break

        # Execute the selected tool
        if tool_name == "python_repl":
            observation = python_repl(tool_input)
        elif tool_name == "web_search":
            observation = web_search(tool_input)
        else:
            observation = "Unknown tool."

        # Feed the result back into the message history
        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "observation", "content": observation})


# 5. RUN
if __name__ == "__main__":
    query = "What is 15% of the current Bitcoin price? Use search to find the price and python for math."
    run_agent(query)
