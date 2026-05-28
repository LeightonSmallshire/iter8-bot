from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from cogs.agent_elmo.deps import AgentDeps
from cogs.agent_elmo.graph import create_agent_graph
from cogs.agent_elmo.sandbox.manager import SandboxManager


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
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(return_value=AIMessage(content="Hello!"))
        mock_get_llm.return_value = mock_llm

        state = {"messages": [HumanMessage(content="Hi")], "channel_id": 123}
        config = {"configurable": {"deps": mock_deps}}

        result = await agent_graph.ainvoke(state, config=config)
        assert result["messages"][-1].content == "Hello!"

@pytest.mark.asyncio
async def test_graph_tool_execution(agent_graph, mock_deps) -> None:
    with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[
            AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}]),
            AIMessage(content="The search result was great!")
        ])
        mock_get_llm.return_value = mock_llm

        # Mock web_search tool to return a value
        # We patch the actual tool function in the module
        with patch("cogs.agent_elmo.tools.web_tools.web_search", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = "Search result: test"

            # We also need to ensure the tool in all_tools is this mock
            # because all_tools is initialized at module load.
            import cogs.agent_elmo.graph as graph_mod
            original_tools = graph_mod.all_tools
            graph_mod.all_tools = [mock_search] + original_tools[1:]

            state = {"messages": [HumanMessage(content="Search for test")], "channel_id": 123}
            config = {"configurable": {"deps": mock_deps}}

            try:
                result = await agent_graph.ainvoke(state, config=config)
                assert "The search result was great!" in result["messages"][-1].content
            finally:
                graph_mod.all_tools = original_tools

@pytest.mark.asyncio
async def test_graph_missing_deps(agent_graph):
    state = {"messages": [HumanMessage(content="Hi")], "channel_id": 123}
    config = {"configurable": {}} # No deps

    with pytest.raises(ValueError, match="AgentDeps missing"):
        await agent_graph.ainvoke(state, config=config)

@pytest.mark.asyncio
async def test_graph_tool_error(agent_graph, mock_deps):
    with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.bind_tools.return_value = mock_llm
        mock_llm.ainvoke = AsyncMock(side_effect=[
            AIMessage(content="", tool_calls=[{"name": "web_search", "args": {"query": "test"}, "id": "call_1"}]),
            AIMessage(content="Fixed it!")
        ])
        mock_get_llm.return_value = mock_llm

        with patch("cogs.agent_elmo.tools.web_tools.web_search", new_callable=AsyncMock) as mock_search:
            mock_search.name = "web_search"
            mock_search.ainvoke.side_effect = Exception("Search failed")

            import cogs.agent_elmo.graph as graph_mod
            original_tools = graph_mod.all_tools
            graph_mod.all_tools = [mock_search] + original_tools[1:]

            state = {"messages": [HumanMessage(content="Search")], "channel_id": 123}
            config = {"configurable": {"deps": mock_deps}}

            result = await agent_graph.ainvoke(state, config=config)
            # The tool error should be captured in a ToolMessage and sent back to LLM
            assert any(isinstance(m, ToolMessage) and "Error executing web_search" in m.content for m in result["messages"])
            graph_mod.all_tools = original_tools
