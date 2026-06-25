from app.agents.state import GraphState
from app.config import PROJECT_ID, GEMINI_MODEL, GEMINI_API_KEY
from google.cloud import bigquery
from google import genai

bq = bigquery.Client(project=PROJECT_ID)

def retrieve_policy_chunks(query: str, top_k: int = 3) -> list:
    """Retrieve relevant policy chunks from BigQuery using keyword matching"""
    words = [w.lower() for w in query.split() if len(w) > 3]
    if not words:
        return []
    conditions = " OR ".join([
        f"LOWER(keywords) LIKE '%{w}%' OR LOWER(content) LIKE '%{w}%'"
        for w in words[:5]
    ])
    sql = f"""
        SELECT chunk_id, topic, content
        FROM retail_mvp.policy_chunks
        WHERE {conditions}
        LIMIT {top_k}
    """
    try:
        rows = list(bq.query(sql).result())
        return [{"topic": r.topic, "content": r.content} for r in rows]
    except Exception as e:
        print(f"[RAG] BigQuery error: {e}")
        return []

def rag_agent_node(state: GraphState) -> GraphState:
    """RAG Agent — retrieves policy chunks and generates grounded response"""
    query = state["query"]
    chunks = retrieve_policy_chunks(query)

    if not chunks:
        return {**state, "response": (
            "I don't have specific information about that policy. "
            "Please contact our support team for assistance."
        )}

    context = "\n\n".join([
        f"[{c['topic'].upper()}]: {c['content']}"
        for c in chunks
    ])

    prompt = f"""You are a retail customer service assistant.
Answer the customer's policy question using ONLY the information provided below.
Do not add information not in the context.
Keep your answer concise and clear — under 80 words.

POLICY INFORMATION:
{context}

Customer question: {query}

Answer:"""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return {**state, "response": response.text, "rag_chunks_used": len(chunks)}
    except Exception as e:
        return {**state, "response": chunks[0]["content"] if chunks else "Please contact our support team.", "error": str(e)}