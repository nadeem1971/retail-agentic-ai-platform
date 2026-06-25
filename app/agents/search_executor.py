from app.agents.state import GraphState
from app.search import search_products

def search_executor_node(state: GraphState) -> GraphState:
    """Search Executor — calls Vertex AI Search"""
    query = state["query"]
    try:
        results, latency_ms = search_products(
            query=query,
            page_size=5
        )
        print(f"[Search Executor] Found {len(results)} products in {latency_ms}ms")
        return {**state, "products": results, "latency_ms": latency_ms}
    except Exception as e:
        print(f"[Search Executor] Error: {e}")
        return {**state, "products": [], "error": str(e)}