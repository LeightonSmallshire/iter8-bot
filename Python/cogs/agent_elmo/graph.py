import os
from typing import Literal, Any

import logfire
from langchain_openai import ChatOpenAI # type: ignore
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

from .state import AgentState
from .deps import AgentDeps
from .tools import web_tools, discord_tools, memory_tools, sandbox_tools

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
        
        # Inject deps into args
        if "bot" in tool_name or "discord" in tool_name:
            args["bot"] = deps.bot
        if "sandbox" in tool_name or "file" in tool_name or "bash" in tool_name:
            args["sandbox"] = deps.sandbox_manager
        if "memory" in tool_name or "remember" in tool_name or "recall" in tool_name:
            args["mem0_client"] = deps.mem0_client
        
        args["channel_id"] = channel_id

        # Find the tool function
        tool_func = next((t for t in all_tools if t.name == tool_name), None)
        if tool_func:
            try:
                res = await tool_func.ainvoke(args)
                tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=str(res)))
            except Exception as e:
                tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=f"Error executing {tool_name}: {str(e)}"))
        else:
            tool_results.append(ToolMessage(tool_call_id=tool_call["id"], content=f"Tool {tool_name} not found."))

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
