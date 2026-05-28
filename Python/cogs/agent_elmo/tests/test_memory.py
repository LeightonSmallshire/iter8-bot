
import pytest

from cogs.agent_elmo.memory.store import AgentMemoryStore


@pytest.fixture
def memory_store(tmp_path) -> AgentMemoryStore:
    db_file = tmp_path / "test_agent.db"
    return AgentMemoryStore(db_path=str(db_file))

def test_checkpoint_save_load(memory_store) -> None:
    # Since we are using LangGraph's SqliteSaver, we test if it can be initialized
    # and if the helper method for cleanup works.
    assert memory_store.get_checkpointer() is not None
    memory_store.cleanup_old_checkpoints() # Should not crash
