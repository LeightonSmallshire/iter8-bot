# import json
# from dataclasses import dataclass
# from huggingface_hub import hf_hub_download

# from langchain.agents import create_agent
# from langchain_community.chat_models import ChatLlamaCpp
# from langchain.tools import tool, ToolRuntime
# from langgraph.checkpoint.memory import InMemorySaver
# from langchain.agents.structured_output import ToolStrategy

# # 1. Download the local model
# # We use Llama-3.2-3B-Instruct as it is highly capable of structured output
# model_path = hf_hub_download(
#     repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
#     filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf"
# )

# # 2. Updated Wrapper to handle strict tool_choice validation


# class CompatibleLlamaCpp(ChatLlamaCpp):
#     """ChatLlamaCpp wrapper that strips tool_choice to avoid validation errors."""

#     def bind_tools(self, tools, **kwargs):
#         # Remove tool_choice entirely. The model will default to using
#         # tools appropriately if they are present in the prompt.
#         kwargs.pop("tool_choice", None)
#         return super().bind_tools(tools, **kwargs)

# # --- Your original logic starts here ---


# SYSTEM_PROMPT = """You are an expert weather forecaster, who speaks in puns.

# You have access to two tools:

# - get_weather_for_location: use this to get the weather for a specific location
# - get_user_location: use this to get the user's location

# If a user asks you for the weather, make sure you know the location. If you can tell from the question that they mean wherever they are, use the get_user_location tool to find their location."""


# @dataclass
# class Context:
#     user_id: str


# @tool
# def get_weather_for_location(city: str) -> str:
#     """Get weather for a given city."""
#     return f"It's always sunny in {city}!"


# @tool
# def get_user_location(runtime: ToolRuntime[Context]) -> str:
#     """Retrieve user information based on user ID."""
#     user_id = runtime.context.user_id
#     return "Florida" if user_id == "1" else "SF"


# # Configure the local model using the compatible wrapper
# model = CompatibleLlamaCpp(
#     model_path=model_path,
#     temperature=0,
#     n_ctx=4096,
#     n_gpu_layers=-1  # Offload to GPU if available
# )


# @dataclass
# class ResponseFormat:
#     punny_response: str
#     weather_conditions: str | None = None


# checkpointer = InMemorySaver()

# agent = create_agent(
#     model=model,
#     system_prompt=SYSTEM_PROMPT,
#     tools=[get_user_location, get_weather_for_location],
#     context_schema=Context,
#     response_format=ToolStrategy(ResponseFormat),
#     checkpointer=checkpointer
# )

# config = {"configurable": {"thread_id": "1"}}

# # Run the agent
# response = agent.invoke(
#     {"messages": [{"role": "user", "content": "what is the weather outside?"}]},
#     config=config,
#     context=Context(user_id="1")
# )

# print(repr(response))
# # print(response['structured_response'])

# response = agent.invoke(
#     {"messages": [{"role": "user", "content": "thank you!"}]},
#     config=config,
#     context=Context(user_id="1")
# )

# print(repr(response))
# # print(response['structured_response'])


# =================================================================================================

import json
import os
import re

from dataclasses import dataclass

from huggingface_hub import hf_hub_download
from langchain.agents import create_agent
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.structured_output import ToolStrategy
from langchain_community.chat_models import ChatLlamaCpp
from langchain_core.messages import ToolCall

# Download or find the model
model_path = hf_hub_download(
    repo_id="bartowski/Llama-3.2-3B-Instruct-GGUF",
    filename="Llama-3.2-3B-Instruct-Q4_K_M.gguf"
)


class LlamaCppCompat(ChatLlamaCpp):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        if tool_choice == 'any':
            tool_choice = None

        return super().bind_tools(tools, tool_choice=tool_choice, **kwargs)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        result = super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
        message = result.generations[0].message
        content = message.content.strip()

        # Regex to find the first valid JSON object {} in the string
        # This handles the "extra bracket" issue by ignoring trailing noise
        json_match = re.search(r'(\{.*\})', content, re.DOTALL)

        if not message.tool_calls and json_match:
            clean_json = json_match.group(1)
            try:
                # Attempt to fix trailing characters if any remain
                # If the model added '}}', this tries to parse only the valid part
                tool_data = json.loads(clean_json)

                if "name" in tool_data:
                    message.tool_calls = [
                        ToolCall(
                            name=tool_data["name"],
                            args=tool_data.get("parameters", {}),
                            id=f"call_{os.urandom(4).hex()}"
                        )
                    ]
                    message.content = ""  # Clear the raw string
            except json.JSONDecodeError:
                # If still broken, we attempt a basic character strip of trailing braces
                try:
                    tool_data = json.loads(clean_json.rstrip('}'))
                    message.tool_calls = [
                        ToolCall(name=tool_data["name"], args=tool_data.get("parameters", {}), id="call_fallback")
                    ]
                    message.content = ""
                except:
                    pass

        return result


# Configure the local model using the compatible wrapper
model = LlamaCppCompat(
    model_path=model_path,
    temperature=0,
    n_ctx=4096,
    n_gpu_layers=-1  # Offload to GPU if available
)

# Define system prompt
SYSTEM_PROMPT = """You are an expert weather forecaster, who speaks in puns.

You have access to two tools:

- get_weather_for_location: use this to get the weather for a specific location
- get_user_location: use this to get the user's location

If a user asks you for the weather, make sure you know the location. If you can tell from the question that they mean wherever they are, use the get_user_location tool to find their location."""

# Define context schema


@dataclass
class Context:
    """Custom runtime context schema."""
    user_id: str

# Define tools


@tool
def get_weather_for_location(city: str) -> str:
    """Get weather for a given city."""
    raise ValueError("asdf")
    return f"It's always sunny in {city}!"


@tool
def get_user_location(runtime: ToolRuntime[Context]) -> str:
    """Retrieve user information based on user ID."""
    user_id = runtime.context.user_id
    raise ValueError("asdf 2")
    return "Florida" if user_id == "1" else "SF"

# # Configure model
# model = init_chat_model(
#     "claude-sonnet-4-5-20250929",
#     temperature=0
# )

# Define response format


@dataclass
class ResponseFormat:
    """Response schema for the agent."""
    # A punny response (always required)
    punny_response: str
    # Any interesting information about the weather if available
    weather_conditions: str | None = None


# Set up memory
checkpointer = InMemorySaver()

# Create agent
agent = create_agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=[get_user_location, get_weather_for_location],
    context_schema=Context,
    response_format=ToolStrategy(ResponseFormat),
    checkpointer=checkpointer
)

# Run agent
# `thread_id` is a unique identifier for a given conversation.
config = {"configurable": {"thread_id": "1"}}

response = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather outside?"}]},
    config=config,
    context=Context(user_id="1")
)

print(response)
print()

for message in response['messages']:
    print(repr(message))

# print(*response['messages'], sep='\n')
exit(0)

print(response['structured_response'])
# ResponseFormat(
#     punny_response="Florida is still having a 'sun-derful' day! The sunshine is playing 'ray-dio' hits all day long! I'd say it's the perfect weather for some 'solar-bration'! If you were hoping for rain, I'm afraid that idea is all 'washed up' - the forecast remains 'clear-ly' brilliant!",
#     weather_conditions="It's always sunny in Florida!"
# )


# Note that we can continue the conversation using the same `thread_id`.
response = agent.invoke(
    {"messages": [{"role": "user", "content": "thank you!"}]},
    config=config,
    context=Context(user_id="1")
)

print(response['structured_response'])
# ResponseFormat(
#     punny_response="You're 'thund-erfully' welcome! It's always a 'breeze' to help you stay 'current' with the weather. I'm just 'cloud'-ing around waiting to 'shower' you with more forecasts whenever you need them. Have a 'sun-sational' day in the Florida sunshine!",
#     weather_conditions=None
# )
