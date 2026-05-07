from dataclasses import dataclass
from pydantic_ai import Agent
from pydantic import BaseModel

import discord
from discord.ext import commands
from .persistence import Persistence
from .docker_manager import DockerManager


class YesNoResponse(BaseModel):
    """Structured response for yes/no questions."""
    answer: bool  # True for yes, False for no


@dataclass
class BaseDeps:
    docker_manager: DockerManager
    channel_id: int


@dataclass
class MainDeps(BaseDeps):
    db: Persistence
    bot: commands.Bot
    mem0_client: Any  # mem0.MemoryClient - will crash if MEM0_API_KEY missing
    # coder_agent: 'CoderAgent'
    # researcher_agent: 'ResearcherAgent'
    # analyst_agent: 'AnalystAgent'
    # yes_no_agent: 'YesNoAgent'


@dataclass
class CoderDeps(BaseDeps):
    pass


@dataclass
class AnalystDeps(BaseDeps):
    pass


@dataclass
class ResearcherDeps(BaseDeps):
    pass


@dataclass
class YesNoDeps(BaseDeps):
    pass


# fmt: off
CoderAgent      = Agent[ CoderDeps     , str           ]
ResearcherAgent = Agent[ ResearcherDeps, str           ]
AnalystAgent    = Agent[ AnalystDeps   , str           ]
YesNoAgent      = Agent[ YesNoDeps     , YesNoResponse ]
# fmt: on
