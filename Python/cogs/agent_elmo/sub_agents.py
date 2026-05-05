from pydantic_ai import Agent
from .deps import CoderDeps, AnalystDeps, ResearcherDeps, YesNoDeps, YesNoResponse, CoderAgent, ResearcherAgent, AnalystAgent, YesNoAgent
from .tools import web_search, docker_exec, docker_read, docker_write


# --- Coder Agent ---
def create_coder_agent() -> CoderAgent:
    """Create a specialized coding agent with Docker tools."""
    agent = Agent("openrouter:openrouter/free", deps_type=CoderDeps)
    agent.tool(docker_exec)
    agent.tool(docker_read)
    agent.tool(docker_write)
    return agent


# --- Researcher Agent ---
def create_researcher_agent() -> ResearcherAgent:
    """Create a specialized research agent with web search."""
    agent = Agent("openrouter:openrouter/free", deps_type=ResearcherDeps)
    agent.tool(web_search)
    return agent


# --- Analyst Agent ---
def create_analyst_agent() -> AnalystAgent:
    """Create a specialized data analysis agent with Docker tools."""
    agent = Agent("openrouter:openrouter/free", deps_type=AnalystDeps)
    agent.tool(docker_exec)
    agent.tool(docker_read)
    agent.tool(docker_write)
    return agent


# --- Yes/No Agent ---
def create_yes_no_agent() -> YesNoAgent:
    """Create a tiny yes/no classifier agent with structured output."""
    agent = Agent("openrouter:openrouter/free", output_type=YesNoResponse, deps_type=YesNoDeps)
    return agent
