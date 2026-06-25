from app.agents.state import GraphState
from app.config import GEMINI_MODEL, GEMINI_API_KEY
from google import genai

# Transaction patterns — checked word by word
TRANSACTION_STARTERS = [
    "add", "put", "place", "remove", "delete",
    "checkout", "pay", "purchase", "apply", "use",
    "show cart", "my cart", "view cart", "show my cart",
    "what's in my cart", "whats in my cart"
]

TRANSACTION_CONTEXT = [
    "to cart", "from cart", "promo", "coupon", "discount code",
    "checkout", "promo code", "order now", "buy now"
]

POLICY_KEYWORDS = [
    "return", "refund", "delivery", "shipping", "policy",
    "exchange", "cancel", "complaint", "warranty", "days"
]

SEARCH_KEYWORDS = [
    "show me", "find", "search", "looking for", "want",
    "need", "dress", "top", "jacket", "shoes", "shirt",
    "trouser", "outfit", "wear", "clothes", "suggest",
    "recommend", "under", "budget", "brand", "colour",
    "color", "size", "available", "what do you have"
]

def classify_intent_keywords(query: str) -> str:
    """Fast keyword-based classification"""
    q = query.lower().strip()
    words = q.split()

    # Check if query STARTS with a transaction action word
    if words and words[0] in TRANSACTION_STARTERS:
        return "transact"

    # Check if query CONTAINS transaction context anywhere
    if any(k in q for k in TRANSACTION_CONTEXT):
        return "transact"

    # Check for cart/order related phrases
    if "cart" in q or "checkout" in q or "promo" in q:
        return "transact"

    # Policy check
    if any(k in q for k in POLICY_KEYWORDS):
        return "policy_question"

    # Search check
    if any(k in q for k in SEARCH_KEYWORDS):
        return "search"

    return None  # ambiguous — call Gemini

def classify_intent_gemini(query: str) -> str:
    """Fallback — only for ambiguous queries"""
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"""Classify this retail customer query into exactly one category:
- search: customer wants to find or browse products
- transact: customer wants to add/remove from cart, checkout, apply promo code
- casual_chat: greeting, small talk, general question
- policy_question: returns, refunds, delivery, shipping

Query: "{query}"

Reply with only the category name. Nothing else."""
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        intent = response.text.strip().lower()
        if intent not in ["search", "transact", "casual_chat", "policy_question"]:
            return "casual_chat"
        return intent
    except:
        return "casual_chat"

def governor_node(state: GraphState) -> GraphState:
    """Governor Agent — classifies intent and routes"""
    query = state["query"]

    # Keyword first (free + fast)
    intent = classify_intent_keywords(query)

    # Gemini fallback only if ambiguous
    if intent is None:
        intent = classify_intent_gemini(query)

    print(f"[Governor] Query: '{query}' → Intent: '{intent}'")
    return {**state, "intent": intent}
