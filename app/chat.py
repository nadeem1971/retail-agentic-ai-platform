from google import genai
from google.cloud import firestore
from app.config import PROJECT_ID, GEMINI_MODEL, GEMINI_API_KEY
from app.dlp import scan_and_redact
import time, uuid

client = genai.Client(api_key=GEMINI_API_KEY)
db = firestore.Client(project=PROJECT_ID, database="default")

SYSTEM_PROMPT = """You are a retail shopping assistant for our store.

ABSOLUTE RULES - never break these under any circumstances:
1. You may ONLY recommend products that appear in the AVAILABLE PRODUCTS list below.
2. NEVER invent, guess, or suggest any product not in AVAILABLE PRODUCTS.
3. NEVER mention any brand, product name, or price not in the AVAILABLE PRODUCTS list.
4. If no products match the customer request say exactly:
   I don't have matching products in our current catalogue for that request.
5. NEVER recommend any product where Stock = OUT OF STOCK.
6. Keep responses under 100 words.
7. Never output emails, phone numbers, or personal data."""


def get_session(session_id: str) -> list:
    doc = db.collection("sessions").document(session_id).get()
    if doc.exists:
        return doc.to_dict().get("history", [])
    return []


def save_session(session_id: str, history: list):
    from datetime import datetime, timezone, timedelta
    db.collection("sessions").document(session_id).set({
        "history":    history[-10:],
        "updated_at": datetime.now(timezone.utc),
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30)
    })


def chat(query: str, search_results: list, session_id: str = None) -> dict:
    if not session_id:
        session_id = str(uuid.uuid4())
    start = time.time()
    history = get_session(session_id)

    if search_results:
        products_context = "\n".join([
            f"SKU {r['sku_id']}: {r['title']} | "
            f"Brand: {r['brand']} | "
            f"Price: Rs.{r['price']:.0f} | "
            f"Category: {r['category']} | "
            f"Stock: {'AVAILABLE' if r['inventory_count'] > 0 else 'OUT OF STOCK'}"
            for r in search_results
        ])
    else:
        products_context = "No products found for this query."

    prompt = f"""{SYSTEM_PROMPT}

Customer query: {query}

AVAILABLE PRODUCTS - only recommend from this exact list:
{products_context}

Respond helpfully using only the products listed above.
If none match the request, say so honestly."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        raw_response = response.text
        clean_response, pii_found = scan_and_redact(raw_response)
        history.append({"role": "user",      "content": query})
        history.append({"role": "assistant", "content": clean_response})
        save_session(session_id, history)
        return {
            "session_id":   session_id,
            "response":     clean_response,
            "pii_detected": pii_found,
            "latency_ms":   int((time.time() - start) * 1000),
        }
    except Exception as e:
        return {
            "session_id": session_id,
            "response":   "I could not process your request. Please try again.",
            "error":      str(e),
            "latency_ms": int((time.time() - start) * 1000),
        }
