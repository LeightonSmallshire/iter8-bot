from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from cogs.agent_elmo.deps import AgentDeps
from cogs.agent_elmo.graph import create_agent_graph
from cogs.agent_elmo.sandbox.manager import SandboxManager

# ---------- helpers ----------

def _real_llm_with_mock_ainvoke(response_or_side_effect):
    """Return a real ChatOpenAI with only the final ainvoke mocked.

    This exercises the real ``bind_tools()`` → ``with_retry()`` chain so that
    ordering bugs (e.g. ``RunnableRetry.bind_tools``) are caught at test time.
    """
    real = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="openrouter/free",
        temperature=0.7,
    )
    # Use object.__setattr__ to bypass Pydantic v2's frozen-field validation
    if isinstance(response_or_side_effect, list):
        object.__setattr__(real, "ainvoke", AsyncMock(side_effect=response_or_side_effect))
    else:
        object.__setattr__(real, "ainvoke", AsyncMock(return_value=response_or_side_effect))
    return real


@pytest.fixture
def agent_graph():
    return create_agent_graph().compile()

@pytest.fixture
def mock_deps() -> AgentDeps:
    return AgentDeps(
        bot=MagicMock(),
        sandbox_manager=SandboxManager(),
        mem0_client=None
    )


@pytest.mark.asyncio
async def test_graph_simple_response(agent_graph, mock_deps) -> None:
    with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
        mock_get_llm.return_value = _real_llm_with_mock_ainvoke([
            AIMessage(content="I should respond briefly"),  # think
            AIMessage(content="Hello!"),                    # agent
        ])

        state = {"messages": [HumanMessage(content="Hi")], "channel_id": 123}
        config = {"configurable": {"deps": mock_deps}}

        result = await agent_graph.ainvoke(state, config=config)
        assert result["messages"][-1].content == "Hello!"


@pytest.mark.asyncio
async def test_graph_tool_execution(agent_graph, mock_deps) -> None:
    with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
        mock_get_llm.return_value = _real_llm_with_mock_ainvoke([
            AIMessage(content="I should search for test"),               # think
            AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}]),
            AIMessage(content="Got results, now respond"),               # think
            AIMessage(content="The search result was great!"),           # agent
        ])

        @tool
        async def web_search(query: str) -> str:
            """Search the web."""
            return "Search result: test"

        import cogs.agent_elmo.graph as graph_mod
        original_tools = graph_mod.all_tools
        graph_mod.all_tools = [web_search] + original_tools[1:]

        state = {"messages": [HumanMessage(content="Search for test")], "channel_id": 123}
        config = {"configurable": {"deps": mock_deps}}

        try:
            result = await agent_graph.ainvoke(state, config=config)
            assert "The search result was great!" in result["messages"][-1].content
        finally:
            graph_mod.all_tools = original_tools


@pytest.mark.asyncio
async def test_graph_missing_deps(agent_graph):
    with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
        mock_get_llm.return_value = _real_llm_with_mock_ainvoke(
            AIMessage(content="I should think briefly"),
        )

        state = {"messages": [HumanMessage(content="Hi")], "channel_id": 123}
        config = {"configurable": {}}  # No deps

        with pytest.raises(ValueError, match="AgentDeps missing"):
            await agent_graph.ainvoke(state, config=config)


@pytest.mark.asyncio
async def test_graph_tool_error(agent_graph, mock_deps):
    with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
        mock_get_llm.return_value = _real_llm_with_mock_ainvoke([
            AIMessage(content="I need to search"),                       # think
            AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}]),
            AIMessage(content="Search failed, I should report it"),      # think
            AIMessage(content="Fixed it!"),                             # agent
        ])

        @tool
        async def web_search(query: str) -> str:
            """Search the web."""
            raise RuntimeError("Search failed")

        import cogs.agent_elmo.graph as graph_mod
        original_tools = graph_mod.all_tools
        graph_mod.all_tools = [web_search] + original_tools[1:]

        state = {"messages": [HumanMessage(content="Search")], "channel_id": 123}
        config = {"configurable": {"deps": mock_deps}}

        result = await agent_graph.ainvoke(state, config=config)
        assert any(
            isinstance(m, ToolMessage) and "Error executing web_search" in m.content
            for m in result["messages"]
        )
        graph_mod.all_tools = original_tools
