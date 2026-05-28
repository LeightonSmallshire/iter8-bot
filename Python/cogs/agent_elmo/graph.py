import inspect
import os
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI  # type: ignore
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .deps import AgentDeps
from .state import AgentState
from .tools import discord_tools, memory_tools, sandbox_tools, web_tools


# --- LLM Setup ---
def get_llm() -> Any:
    """Returns the LLM configured for OpenRouter."""
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY") or "", # type: ignore
        model="openrouter/free",
        temperature=0.7,
    ).with_retry(
        # Use a generic retry policy for transient API errors
        stop_after_attempt=3,
    )

# --- Tool Setup ---
# Collect all tools
all_tools = [
    web_tools.web_search,
    * [t for t in discord_tools.__dict__.values() if callable(t) and hasattr(t, "name") and not t.__name__.startswith("_")],
    * [t for t in memory_tools.__dict__.values() if callable(t) and hasattr(t, "name") and not t.__name__.startswith("_")],
    * [t for t in sandbox_tools.__dict__.values() if callable(t) and hasattr(t, "name") and not t.__name__.startswith("_")],
]

# Create a ToolNode for execution
tool_node = ToolNode(all_tools)

# --- Nodes ---

async def call_agent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Node that calls the LLM to decide the next action."""
    deps = config["configurable"].get("deps")
    if not isinstance(deps, AgentDeps):
        raise ValueError("AgentDeps missing or invalid in config")

    llm = get_llm().bind_tools(all_tools)

    # Persona system prompt
    system_message = {
        "role": "system",
        "content": (
            "You are Iter8, a utility agent with sandboxed filesystem access, bash execution, web search, and Discord controls.\n\n"
            "Be brief. Use your tools proactively. Favor direct answers over explanation.\n"
            "Don't apologize, don't over-explain. Execute the task."
        )
    }

    messages = [system_message] + state["messages"]
    response = await llm.ainvoke(messages)
    return {"messages": [response]}

async def execute_tools(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Node that handles tool execution and injects dependencies."""
    deps = config["configurable"].get("deps")
    if not isinstance(deps, AgentDeps):
        raise ValueError("AgentDeps missing or invalid in config")
    channel_id = state["channel_id"]

    # We wrap the tool node's execution to inject dependencies into tool arguments
    # LangGraph tools can be designed to take 'config' or we can modify the tools
    # For now, we manually map the tools and inject deps

    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        return {"messages": []}

    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"]

        # Find the tool function
        tool_func = next((t for t in all_tools if t.name == tool_name), None)
        if not tool_func:
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=f"Tool {tool_name} not found."))
            continue

        # Inject deps based on function signature
        func = tool_func.func if hasattr(tool_func, "func") else tool_func
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.name == "bot":
                args["bot"] = deps.bot
            elif param.name == "sandbox":
                args["sandbox"] = deps.sandbox_manager
            elif param.name == "mem0_client":
                args["mem0_client"] = deps.mem0_client
            elif param.name == "channel_id":
                args["channel_id"] = channel_id

        try:
            res = await tool_func.ainvoke(args)
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=str(res)))
        except Exception as e:
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=f"Error executing {tool_name}: {str(e)}"))

    return {"messages": tool_results}

def route_after_agent(state: AgentState) -> Literal["tools", "end"]:
    """Conditional edge to decide whether to execute tools or finish."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "end"

# --- Graph Construction ---

def create_agent_graph() -> StateGraph[AgentState]:
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", execute_tools)

    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "end": END})
    workflow.add_edge("tools", "agent")

    return workflow
