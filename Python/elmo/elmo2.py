import json
import os
from dataclasses import dataclass
from huggingface_hub import hf_hub_download

from langchain_community.chat_models import ChatLlamaCpp
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.structured_output import ToolStrategy
from langchain_core.messages import AIMessage, ToolCall

from llama_cpp import LlamaGrammar  # Add this import

# 1. Download Model
model_path = hf_hub_download(
    repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
    filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf"
)

# 2. Optimized Local Model Wrapper


class LocalGrammarModel(ChatLlamaCpp):
    def bind_tools(self, tools, **kwargs):
        kwargs.pop("tool_choice", None)
        return super().bind_tools(tools, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # Define the grammar string
        grammar_text = r"""
            root   ::= object
            object ::= "{" space pairs "}"
            pairs  ::= pair ( "," space pair )*
            pair   ::= string ":" space value
            value  ::= string | number | object | array | "true" | "false" | "null"
            array  ::= "[" space values "]"
            values ::= value ( "," space value )*
            string ::= "\"" [^"\\]* ( "\\" . [^"\\]* )* "\""
            number ::= [0-9]+ ( "." [0-9]+ )?
            space  ::= " "*
        """

        # Compile the grammar string into a LlamaGrammar object
        kwargs["grammar"] = LlamaGrammar.from_string(grammar_text)

        # Call the parent generator
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        message = result.generations[0].message

        # ... rest of your parsing logic ...
        # try:
        data = json.loads(message.content)
        if "name" in data:
            message.tool_calls = [
                ToolCall(
                    name=data["name"],
                    args=data.get("parameters", data.get("args", {})),
                    id=f"call_{os.urandom(2).hex()}"
                )
            ]
            message.content = ""
        # except:
        #     pass

        return result

# --- Agent Configuration ---


@dataclass
class Context:
    user_id: str


@tool
def get_weather_for_location(city: str) -> str:
    """Get weather for a given city."""
    # raise "cheese"
    return f"It's always sunny in {city}!"


@tool
def get_user_location(runtime: ToolRuntime[Context]) -> str:
    """Retrieve user information based on user ID."""
    # raise "baby"
    return "Florida" if runtime.context.user_id == "1" else "SF"


@dataclass
class ResponseFormat:
    punny_response: str
    weather_conditions: str | None = None


model = LocalGrammarModel(
    model_path=model_path,
    temperature=0.1,
    n_ctx=2048,
    n_gpu_layers=-1  # Use -1 for all layers on GPU, or 0 for CPU
)

agent = create_agent(
    model=model,
    system_prompt="You are a punny weather forecaster. If you need a location, use a tool.",
    tools=[get_user_location, get_weather_for_location],
    context_schema=Context,
    response_format=ToolStrategy(ResponseFormat),
    checkpointer=InMemorySaver()
)

# Run
config = {"configurable": {"thread_id": "weather_test"}}
res = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather like in birmingham?"}]},
    config=config,
    context=Context(user_id="1")
)

print(f"Final Response: {res['structured_response']}")
