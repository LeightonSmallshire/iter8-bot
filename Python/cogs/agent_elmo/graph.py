from __future__ import annotations

import inspect
import os
from typing import Any, Literal

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from .deps import AgentDeps
from .state import AgentState
from .tools import discord_tools, memory_tools, reasoning_tools, sandbox_tools, web_tools


# --- LLM Setup ---
def get_llm() -> ChatOpenAI:
    """Returns the base LLM configured for OpenRouter (no retry wrapper)."""
    return ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY") or "", # type: ignore
        model="openrouter/free",
        temperature=0.7,
    )

_sandbox_tools_enabled: bool | None = None

def _check_sandbox_tools() -> bool:
    """Return True if Docker is reachable (cached after first check)."""
    global _sandbox_tools_enabled
    if _sandbox_tools_enabled is not None:
        return _sandbox_tools_enabled
    try:
        import docker
        client = docker.from_env()
        client.ping()
        client.close()
        _sandbox_tools_enabled = True
    except Exception:
        _sandbox_tools_enabled = False
    return _sandbox_tools_enabled

def get_llm_with_tools() -> Any:
    """Returns the LLM with tools bound, wrapped with retry.

    Sandbox tools are only registered when Docker is available —
    otherwise the LLM can't call them, avoiding confusing failures.
    """
    tools = [
        *[t for t in reasoning_tools.__dict__.values() if _is_tool(t)],
        web_tools.web_search,
        web_tools.read_url,
        *[t for t in discord_tools.__dict__.values() if _is_tool(t)],
        *[t for t in memory_tools.__dict__.values() if _is_tool(t)],
    ]
    if _check_sandbox_tools():
        tools.extend(t for t in sandbox_tools.__dict__.values() if _is_tool(t))
    return get_llm().bind_tools(tools).with_retry(stop_after_attempt=3)

# --- Tool Setup ---
# Collect all tools — filter by hasattr(name) + hasattr(description) to match
# StructuredTool instances reliably while excluding modules (e.g. os) that
# happen to have a .name attribute.
def _is_tool(t: Any) -> bool:
    return hasattr(t, "name") and hasattr(t, "description")

all_tools: list[Any] = [
    *[t for t in reasoning_tools.__dict__.values() if _is_tool(t)],
    web_tools.web_search,
    web_tools.read_url,
    *[t for t in discord_tools.__dict__.values() if _is_tool(t)],
    *[t for t in memory_tools.__dict__.values() if _is_tool(t)],
    *[t for t in sandbox_tools.__dict__.values() if _is_tool(t)],
]

# Create a ToolNode for execution
tool_node = ToolNode(all_tools)

# --- Nodes ---

async def think(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Node that produces brief reasoning before the agent acts.

    The output is stored in state['reasoning'] — it is NOT added to the
    message list, so it will never be sent to the user.
    """
    llm = get_llm()
    system_message = {
        "role": "system",
        "content": (
            "You are Iter8's internal reasoning module. Think briefly (1-3 sentences) "
            "about the current situation: what does the user want, what tools might help, "
            "and what to do next. Output only your reasoning."
        )
    }
    messages = [system_message] + state["messages"]
    response = await llm.ainvoke(messages)
    reasoning = response.content
    if isinstance(reasoning, list):
        reasoning = " ".join(
            block["text"] for block in reasoning
            if isinstance(block, dict) and "text" in block
        )
    return {"reasoning": str(reasoning)[:500]}

async def call_agent(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Node that calls the LLM to decide the next action."""
    deps = config["configurable"].get("deps")
    if not isinstance(deps, AgentDeps):
        raise ValueError("AgentDeps missing or invalid in config")

    llm = get_llm_with_tools()

    reasoning = state.get("reasoning", "")
    reasoning_block = f"\n\nYour internal reasoning: {reasoning}" if reasoning else ""

    # Persona system prompt
    system_message = {
        "role": "system",
        "content": (
            "You are Iter8, a utility agent with sandboxed filesystem access, bash execution, web search, and Discord controls.\n\n"
            "Be brief. Use your tools proactively. Favor direct answers over explanation.\n"
            "Don't apologize, don't over-explain. Execute the task.\n\n"
            "Your text output is internal reasoning — it is NEVER shown to the user. "
            "When you are ready to give the final answer, call respond() with that answer. "
            "The respond() content is what the user sees — make it complete and self-contained.\n"
            "Never respond to the user directly as text. Always use respond()."
            f"{reasoning_block}"
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

    responded = any(tc["name"] == "respond" for tc in last_message.tool_calls)

    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        args = tool_call["args"].copy()

        # Find the tool function
        tool_func = next((t for t in all_tools if t.name == tool_name), None)
        if not tool_func:
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=f"Tool {tool_name} not found."))
            continue

        # Inject deps based on function signature
        if hasattr(tool_func, "func") and tool_func.func is not None:
            func = tool_func.func
        elif hasattr(tool_func, "coroutine") and tool_func.coroutine is not None:
            func = tool_func.coroutine
        else:
            func = tool_func
        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.name == "bot":
                args["bot"] = deps.bot
            elif param.name == "sandbox":
                args["sandbox"] = deps.sandbox_manager.get_sandbox()
            elif param.name == "mem0_client":
                args["mem0_client"] = deps.mem0_client
            elif param.name == "channel_id":
                args["channel_id"] = channel_id

        try:
            res = await tool_func.ainvoke(args)
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=str(res)))
        except Exception as e:
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=f"Error executing {tool_name}: {str(e)}"))

    return {"messages": tool_results, "responded": responded}

def route_after_agent(state: AgentState) -> Literal["tools", "end"]:
    """Conditional edge to decide whether to execute tools or finish."""
    last_message = state["messages"][-1]
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    return "end"

def route_after_tools(state: AgentState) -> Literal["think", "end"]:
    """After tool execution, re-think unless the agent already called respond()."""
    if state.get("responded"):
        return "end"
    return "think"

# --- Graph Construction ---

def create_agent_graph() -> StateGraph[AgentState]:
    workflow = StateGraph(AgentState)

    workflow.add_node("think", think)
    workflow.add_node("agent", call_agent)
    workflow.add_node("tools", execute_tools)

    workflow.add_edge(START, "think")
    workflow.add_edge("think", "agent")
    workflow.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "end": END})
    workflow.add_conditional_edges("tools", route_after_tools, {"think": "think", "end": END})

    return workflow
