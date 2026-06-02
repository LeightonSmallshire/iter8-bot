# LangGraph Agent v2 Plan

## 1. Overview
Migration of the `agent_elmo` from PydanticAI to LangGraph to support better sub-agents, persistent state, and a more professional tool-driven architecture.

### Key Decisions
- **Framework:** LangGraph (State-graph based)
- **LLM:** OpenRouter (`openrouter/free`) via `ChatOpenAI`
- **Sandbox:** Unified `Sandbox` protocol supporting both Docker and Modal independently.
- **Persona:** Direct, brief, tool-focused. No unnecessary pleasantries.
- **Persistence:** LangGraph `SqliteSaver` for checkpointing.
- **Streaming:** Disabled (unreliable in Discord).
- **Sub-Agents:** Implemented as sub-graphs called as tools.
- **Error Handling:** `Runnable.with_retry()` on LLM node.
- **Compaction:** Minimal weekly cleanup on bot startup due to low volume.

---

## 2. File Structure
```
agent_elmo/
├── __init__.py               # Clean exports
├── state.py                  # AgentState TypedDict
├── deps.py                   # Runtime dependencies
├── graph.py                  # LangGraph build + compile
├── cog.py                    # AgentCog (Discord integration)
├── util.py                   # split_message, easy_send
├── sandbox/
│   ├── __init__.py           # Sandbox protocol
│   └── manager.py            # Factory + DockerSandbox + ModalSandbox
├── tools/
│   ├── __init__.py
│   ├── sandbox_tools.py      # bash, file_*, run_python
│   ├── web_tools.py          # web_search
│   ├── discord_tools.py      # send_gif, timeout_user, send_message
│   └── memory_tools.py       # remember, recall
└── memory/
    ├── __init__.py
    └── store.py              # SqliteSaver wrapper + weekly cleanup
```

---

## 3. Technical Specifications

### State
- `messages`: `Annotated[list[BaseMessage], add_messages]`
- `channel_id`: `int`

### Graph Flow
1. **`call_agent`**: Calls LLM with current state. Returns AI message.
2. **`execute_tools`**: Runs tool calls and appends results to messages.
3. **`send_response`**: Sends final text to Discord.
4. **Routing**: Conditional edge from `call_agent` $\rightarrow$ `execute_tools` (if tool calls) or $\rightarrow$ `send_response` (if text).

### Sandbox Protocol
Unified interface for `exec`, `read_file`, `write_file`, `list_dir`, `glob`, `grep`, `find`, `mkdir`, `rm`.

### Memory
- Checkpoints saved to `data/agent_storage.db` via `SqliteSaver`.
- Thread ID = `channel_id`.

---

## 4. Implementation Phases
1. **Deps & Skeleton**: `requirements.txt`, directory structure.
2. **Infrastructure**: `state.py`, `deps.py`, `util.py`.
3. **Sandbox Layer**: `sandbox/manager.py` (merging current Docker/Modal logic).
4. **Tool Layer**: Migrating current tools to `tools/` package.
5. **Core Graph**: `graph.py` implementing the state machine.
6. **Memory Layer**: `memory/store.py` implementing checkpointing.
7. **Integration**: Rewriting `elmo_cog.py` to use the graph.
8. **Cleanup**: Deleting old PydanticAI files.
9. **Verification**: Integration testing.
