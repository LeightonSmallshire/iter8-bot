"""Integration tests with minimal mocking — real all_tools, real execute_tools, real graph.

These catch the class of bugs where:
- execute_tools mutates the AIMessage's tool_call args dict (→ json.dumps crash)
- all_tools filter silently drops tools with DI params
- bind_tools fails on non-JSON-serializable types in tool args_schema
"""

import json
from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from cogs.agent_elmo.deps import AgentDeps
from cogs.agent_elmo.graph import all_tools, create_agent_graph, execute_tools
from cogs.agent_elmo.sandbox.manager import SandboxManager

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def deps():
    """Real AgentDeps with mocked components (like the production HotReloadBot)."""
    return AgentDeps(
        bot=MagicMock(),
        sandbox_manager=SandboxManager(),
        mem0_client=None,
    )


@pytest.fixture
def agent_graph():
    return create_agent_graph().compile()


# ---------------------------------------------------------------------------
# all_tools filtering & schema
# ---------------------------------------------------------------------------

class TestAllTools:
    """Verify the tool-discovery filter catches everything and bind_tools works."""

    KNOWN_DI_TOOLS = {
        "send_gif", "timeout_user",              # discord — bot
        "remember", "recall",                    # memory — mem0_client
        "bash", "read_file", "write_file",
        "edit_file", "list_dir", "glob_files",
        "grep_files", "find_files", "make_dir",
        "delete_file", "run_python",             # sandbox — sandbox
    }

    def test_includes_all_di_tools(self):
        """Every tool with DI params must be discoverable in all_tools."""
        names = {t.name for t in all_tools}
        missing = self.KNOWN_DI_TOOLS - names
        assert not missing, f"Tools missing from all_tools: {missing}"

    def test_bind_tools_succeeds(self):
        """Every tool must produce valid JSON schema via bind_tools.
        Regression: PydanticInvalidForJsonSchema on Sandbox protocol type.
        """
        llm = ChatOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key="test-key",
            model="openrouter/free",
            temperature=0.7,
        )
        llm.bind_tools(all_tools)


# ---------------------------------------------------------------------------
# execute_tools — state mutation
# ---------------------------------------------------------------------------

@contextmanager
def _mock_send_gif():
    """Patch external dependencies so send_gif runs without Tenor/Discord."""
    with (
        patch("cogs.agent_elmo.tools.discord_tools.TENOR_KEY", "key"),
        patch("aiohttp.ClientSession.get") as mock_get,
    ):
        mock_response = MagicMock()
        mock_response.json = AsyncMock(return_value={
            "results": [{"media_formats": {"gif": {"url": "https://example.com/cat.gif"}}}],
        })
        mock_get.return_value.__aenter__.return_value = mock_response
        yield


class TestExecuteToolsStateMutation:
    """execute_tools must not contaminate the graph state with DI objects."""

    @pytest.fixture
    def state(self):
        return {
            "messages": [
                AIMessage(content="", tool_calls=[
                    {"name": "send_gif", "args": {"query": "cat"}, "id": "call_1"},
                ]),
            ],
            "channel_id": 1432698704191815680,
        }

    async def test_original_args_are_not_mutated(self, deps, state):
        """The AIMessage's tool_call args dict must be unchanged after execute_tools."""
        original_args = state["messages"][0].tool_calls[0]["args"]

        config = {"configurable": {"deps": deps}}
        with _mock_send_gif():
            await execute_tools(state, config)

        assert original_args == {"query": "cat"}
        assert "bot" not in original_args
        assert "channel_id" not in original_args

    async def test_aimessage_in_state_is_not_contaminated(self, deps, state):
        """The AIMessage stored in state must not contain bot/sandbox etc."""
        config = {"configurable": {"deps": deps}}
        with _mock_send_gif():
            await execute_tools(state, config)

        msg = state["messages"][0]
        args = msg.tool_calls[0]["args"]
        assert "bot" not in args
        assert "channel_id" not in args

    async def test_original_args_are_json_serializable_after_execute(self, deps, state):
        """The AIMessage's tool_call args must survive json.dumps after execution.
        Regression: TypeError('Object of type HotReloadBot is not JSON serializable').
        """
        config = {"configurable": {"deps": deps}}
        with _mock_send_gif():
            await execute_tools(state, config)

        for msg in state["messages"]:
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    json.dumps(tc["args"], ensure_ascii=False)

    async def test_full_message_list_is_json_serializable(self, deps, state):
        """Every message in state (including results) must be JSON-serializable."""
        config = {"configurable": {"deps": deps}}
        with _mock_send_gif():
            result = await execute_tools(state, config)

        all_messages = state["messages"] + result["messages"]
        for msg in all_messages:
            if isinstance(msg, (AIMessage, HumanMessage, ToolMessage)):
                json.dumps(msg.model_dump(mode="json"))

    async def test_repeated_execute_does_not_accumulate_di_objects(self, deps, state):
        """Calling execute_tools multiple times must not compound DI objects in args."""
        config = {"configurable": {"deps": deps}}
        with _mock_send_gif():
            await execute_tools(state, config)
            await execute_tools(state, config)

        args = state["messages"][0].tool_calls[0]["args"]
        assert args == {"query": "cat"}


# ---------------------------------------------------------------------------
# full graph — tools with DI params
# ---------------------------------------------------------------------------

def _mock_llm(sequence):
    """Real ChatOpenAI with only ainvoke mocked — exercises real bind_tools→with_retry."""
    real = ChatOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key="test-key",
        model="openrouter/free",
        temperature=0.7,
    )
    object.__setattr__(real, "ainvoke", AsyncMock(side_effect=sequence))
    return real


@contextmanager
def _mock_bash():
    """Patch SandboxManager.get_sandbox() to return a mock with exec_command."""
    mock_sandbox = AsyncMock()
    mock_sandbox.exec_command = AsyncMock(
        return_value=MagicMock(exit_code=0, output="file1.txt\nfile2.txt")
    )
    with patch.object(SandboxManager, "get_sandbox", return_value=mock_sandbox):
        yield


class TestFullGraphWithDiTools:
    """Full graph runs with tools that need dependency injection."""

    async def test_send_gif(self, agent_graph, deps):
        """Full graph run: send_gif tool → must not crash on second call_agent."""
        with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
            mock_get_llm.return_value = _mock_llm([
                AIMessage(content="I should send a cat GIF"),            # think
                AIMessage(content="", tool_calls=[
                    {"name": "send_gif", "args": {"query": "cat"}, "id": "call_1"},
                ]),
                AIMessage(content="GIF sent, now respond"),              # think
                AIMessage(content="Sent a cat GIF!"),
            ])

            state = {"messages": [HumanMessage(content="send a cat gif")], "channel_id": 123}
            config = {"configurable": {"deps": deps}}

            with _mock_send_gif():
                result = await agent_graph.ainvoke(state, config=config)

            assert "cat" in result["messages"][-1].content

    async def test_bash(self, agent_graph, deps):
        """Full graph run: bash tool (sandbox injection) → must not crash."""
        with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
            mock_get_llm.return_value = _mock_llm([
                AIMessage(content="I should list files"),                # think
                AIMessage(content="", tool_calls=[
                    {"name": "bash", "args": {"command": "ls"}, "id": "call_1"},
                ]),
                AIMessage(content="Files listed, now respond"),          # think
                AIMessage(content="Listed files!"),
            ])

            state = {"messages": [HumanMessage(content="list files")], "channel_id": 123}
            config = {"configurable": {"deps": deps}}

            with _mock_bash():
                result = await agent_graph.ainvoke(state, config=config)

            assert "Listed" in result["messages"][-1].content

    async def test_remember(self, agent_graph):
        """Full graph run: remember tool (mem0 injection) → must not crash."""
        mock_mem0 = MagicMock()

        deps_with_mem0 = AgentDeps(
            bot=MagicMock(),
            sandbox_manager=SandboxManager(),
            mem0_client=mock_mem0,
        )

        with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
            mock_get_llm.return_value = _mock_llm([
                AIMessage(content="I should remember the answer"),       # think
                AIMessage(content="", tool_calls=[
                    {"name": "remember", "args": {"content": "the answer is 42"}, "id": "call_1"},
                ]),
                AIMessage(content="Remembered, now respond"),            # think
                AIMessage(content="Remembered!"),
            ])

            state = {"messages": [HumanMessage(content="remember 42")], "channel_id": 123}
            config = {"configurable": {"deps": deps_with_mem0}}

            result = await agent_graph.ainvoke(state, config=config)

            assert "Remembered" in result["messages"][-1].content
            mock_mem0.add.assert_called_once()

    async def test_all_three_di_tools_serializable(self, agent_graph, deps):
        """After a full graph run with a DI tool, the final state must be serializable."""
        with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
            mock_get_llm.return_value = _mock_llm([
                AIMessage(content="I should run pwd"),                   # think
                AIMessage(content="", tool_calls=[
                    {"name": "bash", "args": {"command": "pwd"}, "id": "call_1"},
                ]),
                AIMessage(content="Done, now respond"),                  # think
                AIMessage(content="Done"),
            ])

            state = {"messages": [HumanMessage(content="pwd")], "channel_id": 123}
            config = {"configurable": {"deps": deps}}

            with _mock_bash():
                result = await agent_graph.ainvoke(state, config=config)

            for msg in list(state["messages"]) + result["messages"]:
                if hasattr(msg, "model_dump"):
                    json.dumps(msg.model_dump(mode="json"))

    async def test_consecutive_tool_calls(self, agent_graph, deps):
        """Two consecutive tool call cycles must not corrupt state."""
        with patch("cogs.agent_elmo.graph.get_llm") as mock_get_llm:
            mock_get_llm.return_value = _mock_llm([
                AIMessage(content="I should run two commands"),          # think
                AIMessage(content="", tool_calls=[
                    {"name": "bash", "args": {"command": "echo 1"}, "id": "call_1"},
                ]),
                AIMessage(content="First done, run second"),             # think
                AIMessage(content="", tool_calls=[
                    {"name": "bash", "args": {"command": "echo 2"}, "id": "call_2"},
                ]),
                AIMessage(content="All done, now respond"),              # think
                AIMessage(content="All done"),
            ])

            state = {"messages": [HumanMessage(content="run two commands")], "channel_id": 123}
            config = {"configurable": {"deps": deps}}

            with _mock_bash():
                result = await agent_graph.ainvoke(state, config=config)

            assert "done" in result["messages"][-1].content.lower()
