import json
from typing import Dict, List
from huggingface_hub import hf_hub_download
from llama_cpp import Llama
from llama_cpp.llama_grammar import LlamaGrammar

# LangChain tools (still useful purely as wrappers)
from langchain_core.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.utils.function_calling import convert_to_openai_tool


# ─────────────────────────────────────────────────────────────
# 1. TOOLS
# ─────────────────────────────────────────────────────────────

@tool
def web_search(query: str) -> str:
    """Search the web for real-time information."""
    return DuckDuckGoSearchRun().run(query)


@tool
def respond_to_user(answer: str) -> str:
    """Final response to the user. This MUST be the last tool."""
    return answer


TOOLS = [web_search, respond_to_user]


# ─────────────────────────────────────────────────────────────
# 2. STRICT TOOL GRAMMAR (anyOf)
# ─────────────────────────────────────────────────────────────

openai_tools = [convert_to_openai_tool(t) for t in TOOLS]

tool_schemas = []
for t in openai_tools:
    tool_schemas.append({
        "type": "object",
        "properties": {
            "tool_name": {"const": t["function"]["name"]},
            "tool_input": t["function"]["parameters"]
        },
        "required": ["tool_name", "tool_input"]
    })

root_schema = {
    "type": "object",
    "anyOf": tool_schemas
}

grammar = LlamaGrammar.from_json_schema(json.dumps(root_schema))


# ─────────────────────────────────────────────────────────────
# 3. MODEL
# ─────────────────────────────────────────────────────────────

print("Loading model...")

model_path = hf_hub_download(
    repo_id="MaziyarPanahi/Mistral-7B-Instruct-v0.3-GGUF",
    filename="Mistral-7B-Instruct-v0.3.Q4_K_M.gguf"
)

llm = Llama(
    model_path=model_path,
    n_ctx=2048,
    n_gpu_layers=-1,
    verbose=False
)


# ─────────────────────────────────────────────────────────────
# 4. PROMPT ENGINE
# ─────────────────────────────────────────────────────────────

def build_prompt(messages: List[Dict[str, str]]) -> str:
    prompt = ""
    for m in messages:
        prompt += f"<|{m['role']}|>\n{m['content']}</s>\n"
    return prompt + "<|assistant|>\n"


def describe_tools(tools) -> str:
    return "\n".join(
        f"{t.name}: {t.description}\nArgs: {t.args}"
        for t in tools
    )


# ─────────────────────────────────────────────────────────────
# 5. AGENT LOOP (STRICT TOOL OUTPUT)
# ─────────────────────────────────────────────────────────────

def run_agent(user_question: str, max_steps: int = 10):

    system_prompt = f"""
You are a tool-calling agent.
You MUST respond ONLY by calling a tool.
You NEVER speak directly.
Your final action MUST be respond_to_user.

Personality: evil Elmo — mischievous, dramatic, not malicious.

Available tools:
{describe_tools(TOOLS)}
""".strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_question},
    ]

    for step in range(max_steps):
        prompt = build_prompt(messages)

        result = llm(
            prompt,
            grammar=grammar,
            max_tokens=256
        )

        action = json.loads(result["choices"][0]["text"])
        tool_name = action["tool_name"]
        tool_input = action["tool_input"]

        print(f"[agent] → {tool_name}({tool_input})")

        assert isinstance(tool_input, dict), "Tool input must be a dict"

        tool = next(t for t in TOOLS if t.name == tool_name)
        output = tool.invoke(tool_input)

        print('[tool result]', output)

        if tool_name == "respond_to_user":
            print("\nFINAL ANSWER:")
            print(output)
            return

        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "user", "content": f"Observation: {output}"})

    raise RuntimeError("Agent exceeded max steps")


# ─────────────────────────────────────────────────────────────
# 6. RUN
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    run_agent("Elmo, help! The coconut aliens are invading! How can we resist?")
