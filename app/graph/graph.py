"""Build and compile the LangGraph conversation graph.

Graph flow:
    START → memory_injection → router → [skin | report | chat] → response_formatter → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    chat_responder,
    memory_injection,
    report_analyzer,
    response_formatter,
    router,
    skin_analyzer,
)
from app.graph.state import ConversationState


def build_conversation_graph() -> StateGraph:
    """Build and compile the conversation graph."""
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("memory_injection", memory_injection)
    graph.add_node("skin_analyzer", skin_analyzer)
    graph.add_node("report_analyzer", report_analyzer)
    graph.add_node("chat_responder", chat_responder)
    graph.add_node("response_formatter", response_formatter)

    # Set entry point
    graph.set_entry_point("memory_injection")

    # Add conditional edges from memory_injection to router
    graph.add_conditional_edges(
        "memory_injection",
        router,
        {
            "skin": "skin_analyzer",
            "report": "report_analyzer",
            "chat": "chat_responder",
        },
    )

    # All analysis/chat nodes converge to response_formatter
    graph.add_edge("skin_analyzer", "response_formatter")
    graph.add_edge("report_analyzer", "response_formatter")
    graph.add_edge("chat_responder", "response_formatter")

    # response_formatter → END
    graph.add_edge("response_formatter", END)

    return graph.compile()


# Singleton compiled graph instance
conversation_graph = build_conversation_graph()