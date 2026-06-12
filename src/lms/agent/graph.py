"""LangGraph SOP wrapper (IMDA structural control; Phase 8)."""

from __future__ import annotations

from typing import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


class AgentGraphState(TypedDict, total=False):
    step: str
    halted: bool


def build_issue_sop_graph() -> StateGraph:
    """Minimal SOP graph documenting fixed edges; coordinator owns business logic."""

    def enter(_: AgentGraphState) -> AgentGraphState:
        return {"step": "parse", "halted": False}

    def parse(state: AgentGraphState) -> AgentGraphState:
        return {**state, "step": "govern"}

    def govern(state: AgentGraphState) -> AgentGraphState:
        return {**state, "step": "respond"}

    builder = StateGraph(AgentGraphState)
    builder.add_node("enter", enter)
    builder.add_node("parse", parse)
    builder.add_node("govern", govern)
    builder.add_edge(START, "enter")
    builder.add_edge("enter", "parse")
    builder.add_edge("parse", "govern")
    builder.add_edge("govern", END)
    return builder


def compile_issue_sop_graph():
    checkpointer = MemorySaver()
    return build_issue_sop_graph().compile(checkpointer=checkpointer)
