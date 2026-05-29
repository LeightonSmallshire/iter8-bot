from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """The state of the LangGraph agent."""
    # add_messages is a reducer that appends new messages to the list
    messages: Annotated[list[BaseMessage], add_messages]
    channel_id: int
    responded: bool
    reasoning: str
