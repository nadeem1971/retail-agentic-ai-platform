from app.agents.state import GraphState
from app.config import GEMINI_MODEL, GEMINI_API_KEY
from google import genai

CASUAL_PROMPT = """You are a friendly retail shopping assistant.
Answer the customer's question helpfully and briefly.
Keep responses under 80 words.
Do not recommend specific products unless asked."""

POLICY_PROMPT = """You are a retail customer service assistant.
Answer policy questions helpfully.
Standard policies:
- Returns: 30 days with receipt
- Delivery: 3-5 business days
- Refunds: processed in 5-7 business days
- Exchange: available within 30 days
Keep responses under 80 words."""

def chat_node(state: GraphState) -> GraphState:
    """Handles casual chat and policy questions"""
    query = state["query"]
    intent = state["intent"]
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        system = POLICY_PROMPT if intent == "policy_question" else CASUAL_PROMPT
        prompt = f"{system}\n\nCustomer: {query}"
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return {**state, "response": response.text}
    except Exception as e:
        return {**state, "response": "I am here to help! Please ask me about our products.", "error": str(e)}