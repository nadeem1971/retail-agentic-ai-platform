from app.agents.state import GraphState
from app.config import GEMINI_MODEL, GEMINI_API_KEY
from app.dlp import scan_and_redact
from google import genai

SYSTEM_PROMPT = """You are a retail shopping assistant.
ABSOLUTE RULES:
1. ONLY recommend products from AVAILABLE PRODUCTS list
2. Never invent products not in the list
3. Never recommend OUT OF STOCK items
4. If nothing matches say: I don't have matching products for that request
5. Keep responses under 100 words"""

def generator_node(state: GraphState) -> GraphState:
    """Generator — formats final response using Gemini + DLP scan"""
    query    = state["query"]
    products = state.get("products", [])

    if not products:
        return {**state, "response": "I don't have matching products in our current catalogue for that request."}

    products_context = "\n".join([
        f"SKU {r['sku_id']}: {r['title']} | Brand: {r['brand']} | "
        f"Price: Rs.{r['price']:.0f} | "
        f"Stock: {'AVAILABLE' if r['inventory_count'] > 0 else 'OUT OF STOCK'}"
        for r in products
    ])

    prompt = f"""{SYSTEM_PROMPT}

Customer query: {query}

AVAILABLE PRODUCTS:
{products_context}

Respond helpfully using only the products above."""

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        clean_response, _ = scan_and_redact(response.text)
        return {**state, "response": clean_response}
    except Exception as e:
        return {**state, "response": "I could not process your request. Please try again.", "error": str(e)}