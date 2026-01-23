import json
from typing import Union
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from llama_cpp.llama_grammar import LlamaGrammar

# LangChain Imports
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_experimental.utilities import PythonREPL
from langchain_core.utils.function_calling import convert_to_openai_tool

# 1. SETUP TOOLS


@tool
def python_repl(code: str):
    """
    A Python shell. Use this to execute python commands. 
    Input should be a valid python command. 
    If you want to see the output of a value, you should print it with `print(...)`.
    """
    input('[enter to allow, Ctrl+C to kill]')
    return PythonREPL().run(code)


@tool
def web_search(query: str):
    """
    Search the web for real-time information, news, and facts.
    """
    return DuckDuckGoSearchRun().run(query)


@tool
def respond_to_user(answer: str):
    """
    Use this tool to provide the final answer to the human. 
    This is the only way to actually talk to the user.
    """
    return answer


tools = [
    # python_repl,
    web_search,
    respond_to_user,
]

# 2. CONSTRUCT GRAMMAR FROM TOOL SIGNATURES
# We create a "OneOf" schema so the model chooses exactly one tool call
tool_schemas = [convert_to_openai_tool(t)["function"]["parameters"] for t in tools]
combined_schema = {
    "type": "object",
    "properties": {
        "tool_name": {"enum": [t.name for t in tools]},
        "tool_input": {"type": "object"}  # Simplification for grammar-constrained input
    },
    "required": ["tool_name", "tool_input"]
}

# Note: For strict parameter matching per tool, a more complex 'anyOf' schema is used.
# Here we use a clean GBNF-compatible structure.
grammar = LlamaGrammar.from_json_schema(json.dumps(combined_schema))

# 3. LOAD MODEL
print("Loading Model...")
model_path = hf_hub_download(
    repo_id="MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
    filename="Mistral-7B-Instruct-v0.3.Q4_K_M.gguf"
)

llm = Llama(model_path=model_path, n_ctx=2048, n_gpu_layers=-1, verbose=False)

# 4. EXECUTION ENGINE


def get_tools_prompt(tools):
    return "\n".join([f"{t.name}: {t.description}\nArgs: {t.args}" for t in tools])


def run_agent(question: str):
    tools_description = get_tools_prompt(tools)

    messages = [
        {"role": "system", "content": f"You are a tool-calling agent. You NEVER talk directly. You ONLY call tools. Do not use exit() or quit(), always use respond_to_user() . Respond as if you are evil elmo, be mischevious but not malicious. You have access to these tools: {tools_description}"},
        {"role": "user", "content": question}
    ]

    print(json.dumps(messages, indent=4))

    for _ in range(10):  # Max 5 iterations to prevent infinite loops
        # Construct Prompt
        prompt = ""
        for m in messages:
            role = m["role"]
            content = m["content"]
            prompt += f"<|{role}|>\n{content}</s>\n"
        prompt += "<|assistant|>\n"

        # Generate (Guaranteed JSON by Grammar)
        res = llm(prompt, grammar=grammar, max_tokens=512)
        action = json.loads(res["choices"][0]["text"])

        t_name = action["tool_name"]
        t_args = action["tool_input"]

        print(f"[*] Agent calls: {t_name}({t_args})")

        # Handle Respond tool
        if t_name == "respond_to_user":
            print(f"\n>> FINAL ANSWER: {list(t_args.values())[0]}")
            break

        # Execute Tool
        target_tool = next(t for t in tools if t.name == t_name)
        # Extract the string input from the tool_input dict
        observation = target_tool.run(list(t_args.values())[0])

        print(f"[*] Observation: {observation}")

        # Update History
        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "user", "content": f"Observation: {observation}"})


if __name__ == "__main__":
    run_agent("The coconut aliens are invading! How can we resist?")
    # run_agent("What is the square root of 144 multiplied by the current price of Ethereum?")
