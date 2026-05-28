from dataclasses import dataclass
from typing import Any

from discord.ext import commands


@dataclass
class AgentDeps:
    """Runtime dependencies for the LangGraph agent."""
    bot: commands.Bot
    sandbox_manager: Any  # SandboxManager instance
    mem0_client: Any = None # Optional mem0 client
