from dataclasses import dataclass
from typing import Any

from discord.ext import commands
from pydantic import BaseModel
from pydantic_ai import Agent

from .modal_manager import ModalManager
from .persistence import Persistence


class YesNoResponse(BaseModel):
    """Structured response for yes/no questions."""

    answer: bool  # True for yes, False for no


@dataclass
class BaseDeps:
    docker_manager: ModalManager  # Using ModalManager (interface-compatible with DockerManager)
    channel_id: int


@dataclass
class MainDeps(BaseDeps):
    db: Persistence
    bot: commands.Bot
    mem0_client: Any  # mem0.MemoryClient - will crash if MEM0_API_KEY missing


@dataclass
class YesNoDeps(BaseDeps):
    pass


# fmt: off
YesNoAgent = Agent[ YesNoDeps, YesNoResponse ]
# fmt: on
