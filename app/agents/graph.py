from langgraph.graph import StateGraph, END
from app.agents.state import GraphState
from app.agents.governor import governor_node
from app.agents.search_executor import search_executor_node
from app.agents.generator import generator_node
from app.agents.chat_node import chat_node
from app.agents.rag_agent import rag_agent_node
from app.agents.transaction_executor import transaction_executor_node
from app.agents.policy_watcher import policy_watcher_node

def route_intent(state: GraphState) -> str:
    intent = state.get("intent", "casual_chat")
    if intent == "search":
        return "search_executor"
    if intent == "transact":
        return "transaction_executor"
    if intent == "policy_question":
        return "rag_agent"
    return "chat_node"

def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("governor",             governor_node)
    graph.add_node("search_executor",      search_executor_node)
    graph.add_node("generator",            generator_node)
    graph.add_node("chat_node",            chat_node)
    graph.add_node("rag_agent",            rag_agent_node)
    graph.add_node("transaction_executor", transaction_executor_node)
    graph.add_node("policy_watcher",       policy_watcher_node)

    graph.set_entry_point("governor")

    graph.add_conditional_edges(
        "governor",
        route_intent,
        {
            "search_executor":      "search_executor",
            "transaction_executor": "transaction_executor",
            "rag_agent":            "rag_agent",
            "chat_node":            "chat_node",
        }
    )

    graph.add_edge("search_executor",      "generator")
    graph.add_edge("generator",            "policy_watcher")
    graph.add_edge("rag_agent",            "policy_watcher")
    graph.add_edge("chat_node",            "policy_watcher")
    graph.add_edge("transaction_executor", "policy_watcher")
    graph.add_edge("policy_watcher",       END)

    return graph.compile()

retail_graph = build_graph()
