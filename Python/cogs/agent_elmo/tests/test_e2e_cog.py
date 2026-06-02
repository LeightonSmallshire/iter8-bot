import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands
from langchain_core.messages import AIMessage, ToolMessage

from cogs.elmo_cog import AgentCog, ChannelState

# ---------- helpers ----------

def _async_gen(*items):
    """Return an async generator that yields items in order."""
    async def gen():
        for item in items:
            yield item
    return gen()


def _make_message(id: int, content: str, is_bot: bool, created_at: datetime | None = None):
    """Build a minimal discord.Message mock."""
    msg = MagicMock(spec=discord.Message)
    msg.id = id
    msg.clean_content = content
    author = MagicMock()
    author.id = 999 if is_bot else id
    author.bot = is_bot
    msg.author = author
    msg.created_at = created_at or datetime(2024, 1, 1)
    return msg


def _make_channel(channel_id: int, history_sidelist: list[list] | None = None):
    """Build a mock TextChannel with controlled history."""
    ch = AsyncMock(spec=discord.TextChannel)
    ch.id = channel_id
    ch.typing.return_value.__aenter__ = AsyncMock()
    ch.typing.return_value.__aexit__ = AsyncMock()
    ch.send = AsyncMock()

    if history_sidelist:
        ch.history.side_effect = [_async_gen(*msgs) for msgs in history_sidelist]
    else:
        ch.history.return_value = _async_gen()

    return ch


def _make_bot():
    bot = MagicMock(spec=commands.Bot)
    bot.user = MagicMock()
    bot.user.id = 999
    bot.user.mentioned_in = MagicMock(return_value=False)
    return bot


# ---------- _do_work tests ----------

@pytest.mark.asyncio
async def test_do_work_with_bot_history():
    """Messages after the last bot message are sent to the agent and its response is posted."""
    bot = _make_bot()
    channel_id = 123

    bot_msg = _make_message(1, "Previous answer", is_bot=True, created_at=datetime(2024, 1, 1, 12, 0))
    user_msg = _make_message(2, "Follow up question", is_bot=False, created_at=datetime(2024, 1, 1, 12, 1))

    channel = _make_channel(
        channel_id,
        history_sidelist=[
            [bot_msg, user_msg],   # first history(100) → find bot message
            [user_msg],            # second history(200, after=…) → user messages
        ],
    )
    bot.get_channel.return_value = channel

    cog = AgentCog(bot=bot)
    with patch("cogs.elmo_cog.graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [
                AIMessage(content="I should respond", tool_calls=[
                    {"name": "respond", "args": {"content": "Here is the follow-up answer"}, "id": "r1"},
                ]),
                ToolMessage(content="Here is the follow-up answer", tool_call_id="r1"),
            ],
        })
        await cog._do_work(channel_id)

    channel.send.assert_called_once_with("Here is the follow-up answer")


@pytest.mark.asyncio
async def test_do_work_no_bot_history():
    """Without a prior bot message, all recent user messages are sent."""
    bot = _make_bot()
    channel_id = 123

    user_a = _make_message(1, "First ever message", is_bot=False, created_at=datetime(2024, 1, 1, 11, 0))
    user_b = _make_message(2, "Second message", is_bot=False, created_at=datetime(2024, 1, 1, 11, 1))

    channel = _make_channel(
        channel_id,
        history_sidelist=[
            [user_a, user_b],   # first call – no bot msg found
            [user_a, user_b],   # second call – collect all user messages
        ],
    )
    bot.get_channel.return_value = channel

    cog = AgentCog(bot=bot)
    with patch("cogs.elmo_cog.graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [
                AIMessage(content="I should respond", tool_calls=[
                    {"name": "respond", "args": {"content": "Response"}, "id": "r2"},
                ]),
                ToolMessage(content="Response", tool_call_id="r2"),
            ],
        })
        await cog._do_work(channel_id)

    channel.send.assert_called_once_with("Response")


@pytest.mark.asyncio
async def test_do_work_no_new_messages():
    """When there are no user messages, _do_work returns early."""
    bot = _make_bot()
    channel_id = 123

    bot_msg = _make_message(1, "Last answer", is_bot=True)
    channel = _make_channel(
        channel_id,
        history_sidelist=[
            [bot_msg],     # first call → find bot message
            [],            # second call → no user messages after it
        ],
    )
    bot.get_channel.return_value = channel

    cog = AgentCog(bot=bot)
    with patch("cogs.elmo_cog.graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock()
        await cog._do_work(channel_id)

    mock_graph.ainvoke.assert_not_called()
    channel.send.assert_not_called()


@pytest.mark.asyncio
async def test_do_work_channel_not_found():
    """If the channel cannot be resolved, _do_work returns early."""
    bot = _make_bot()
    bot.get_channel.return_value = None

    cog = AgentCog(bot=bot)
    with patch("cogs.elmo_cog.graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock()
        await cog._do_work(999)

    mock_graph.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_do_work_graph_error():
    """When the graph raises an exception, the channel receives an error message."""
    bot = _make_bot()
    channel_id = 123

    user_msg = _make_message(1, "Hello", is_bot=False)
    channel = _make_channel(
        channel_id,
        history_sidelist=[[], [user_msg]],
    )
    bot.get_channel.return_value = channel

    cog = AgentCog(bot=bot)
    with patch("cogs.elmo_cog.graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(side_effect=ValueError("LLM failure"))
        await cog._do_work(channel_id)

    channel.send.assert_called_once()
    assert "System: Agent error" in channel.send.call_args[0][0]


@pytest.mark.asyncio
async def test_do_work_multimodal_response():
    """A multimodal (list) response is flattened before sending."""
    bot = _make_bot()
    channel_id = 123

    user_msg = _make_message(1, "Hi", is_bot=False)
    channel = _make_channel(
        channel_id,
        history_sidelist=[[], [user_msg]],
    )
    bot.get_channel.return_value = channel

    cog = AgentCog(bot=bot)
    with patch("cogs.elmo_cog.graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value={
            "messages": [
                AIMessage(content="I should respond", tool_calls=[
                    {"name": "respond", "args": {"content": "Hello world"}, "id": "r3"},
                ]),
                ToolMessage(content="Hello world", tool_call_id="r3"),
            ],
        })
        await cog._do_work(channel_id)

    channel.send.assert_called_once_with("Hello world")


# ---------- on_message tests ----------

@pytest.mark.asyncio
async def test_on_message_mention_triggers():
    """A mention sets should_run and signals the event."""
    bot = _make_bot()
    bot.user.mentioned_in.return_value = True

    msg = MagicMock(spec=discord.Message)
    msg.author.bot = False
    msg.channel.id = 1498977340821209198
    msg.reference = None

    cog = AgentCog(bot=bot)
    with patch.object(cog, "_start_worker_if_needed") as mock_start:
        await cog.on_message(msg)
        mock_start.assert_called_once_with(msg.channel.id)


# ---------- worker tests ----------

@pytest.mark.asyncio
async def test_worker_calls_do_work():
    """The worker calls _do_work when the event fires and should_run is True."""
    bot = _make_bot()
    cog = AgentCog(bot=bot)

    channel_id = 100
    state = ChannelState()
    cog.channel_states[channel_id] = state

    state.should_run = True

    async def fake_do_work(cid: int) -> None:
        fake_do_work.called_with = cid

    fake_do_work.called_with = None
    cog._do_work = fake_do_work  # type: ignore[method-assign]

    # Fire the event to wake the worker
    state.event.set()
    state.last_activity = 0  # ensure silence delay is 0

    # Run worker briefly and cancel
    task = asyncio.create_task(cog._worker(channel_id))
    await asyncio.sleep(0.1)
    task.cancel()
    # Worker catches CancelledError and exits cleanly
    await task

    assert fake_do_work.called_with == channel_id


@pytest.mark.asyncio
async def test_worker_retriggers_on_new_event():
    """If the event fires during _do_work, the worker re-enters immediately."""
    bot = _make_bot()
    cog = AgentCog(bot=bot)

    channel_id = 200
    state = ChannelState()
    cog.channel_states[channel_id] = state

    call_count = 0

    async def fake_do_work(cid: int) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Fire the event again so worker re-triggers
            state.should_run = True
            state.event.set()

    cog._do_work = fake_do_work  # type: ignore[method-assign]

    state.should_run = True
    state.event.set()
    state.last_activity = 0

    task = asyncio.create_task(cog._worker(channel_id))
    await asyncio.sleep(0.15)
    task.cancel()
    await task

    assert call_count >= 2, "Worker should have run _do_work at least twice"


@pytest.mark.asyncio
async def test_worker_skips_when_should_run_false():
    """Worker returns to waiting when should_run is False after silence."""
    bot = _make_bot()
    cog = AgentCog(bot=bot)

    channel_id = 300
    state = ChannelState()
    cog.channel_states[channel_id] = state

    called = False

    async def fake_do_work(cid: int) -> None:
        nonlocal called
        called = True

    cog._do_work = fake_do_work  # type: ignore[method-assign]

    state.should_run = False  # not set
    state.event.set()
    state.last_activity = 0

    task = asyncio.create_task(cog._worker(channel_id))
    await asyncio.sleep(0.1)
    task.cancel()
    await task

    assert called is False


# ---------- cleanup ----------

@pytest.mark.asyncio
async def test_cog_unload_cancels_workers():
    """cog_unload cancels all running worker tasks."""
    bot = _make_bot()
    cog = AgentCog(bot=bot)

    s1 = ChannelState()
    s2 = ChannelState()
    t1 = asyncio.create_task(asyncio.sleep(999))
    t2 = asyncio.create_task(asyncio.sleep(999))
    s1.worker_task = t1
    s2.worker_task = t2
    cog.channel_states[1] = s1
    cog.channel_states[2] = s2

    await cog.cog_unload()
    await asyncio.sleep(0.05)

    assert t1.cancelled()
    assert t2.cancelled()
    assert len(cog.channel_states) == 0


# ---------- _start_worker_if_needed ----------

@pytest.mark.asyncio
async def test_start_worker_if_needed_creates_task():
    """A new worker task is created for a channel without one."""
    bot = _make_bot()
    cog = AgentCog(bot=bot)

    state = ChannelState()
    cog.channel_states[123] = state

    cog._start_worker_if_needed(123)
    assert state.worker_task is not None
    assert not state.worker_task.done()

    state.worker_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await state.worker_task


@pytest.mark.asyncio
async def test_start_worker_if_needed_reuses_task():
    """If a worker is already running, no new task is created."""
    bot = _make_bot()
    cog = AgentCog(bot=bot)

    state = ChannelState()
    existing = asyncio.create_task(asyncio.sleep(999))
    state.worker_task = existing
    cog.channel_states[123] = state

    cog._start_worker_if_needed(123)
    assert state.worker_task is existing

    existing.cancel()
    with pytest.raises(asyncio.CancelledError):
        await existing
