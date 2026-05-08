from pydantic_ai import Agent

from .deps import YesNoAgent, YesNoDeps, YesNoResponse


# --- Yes/No Agent ---
def create_yes_no_agent() -> YesNoAgent:
    """Create a tiny yes/no classifier agent with structured output."""
    agent = Agent("openrouter:openrouter/free", output_type=YesNoResponse, deps_type=YesNoDeps)
    return agent
