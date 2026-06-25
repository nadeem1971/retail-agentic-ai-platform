from app.agents.state import GraphState
from app.agents.cart import add_item, remove_item, apply_promo, get_cart
from app.agents.risk_engine import calculate_risk_score
from app.search import search_products
from google.cloud import bigquery
import uuid
from datetime import datetime, timezone
from app.agents.mcp_notifier import notify_order_confirmed

bq = bigquery.Client(project="retail-ai-mvp")

TRANSACTION_KEYWORDS = {
    "add":      ["add", "put", "place", "include"],
    "remove":   ["remove", "delete", "take out"],
    "promo":    ["promo", "coupon", "discount", "code", "offer"],
    "checkout": ["checkout", "pay", "buy now", "order"],
    "view":     ["show cart", "my cart", "view cart", "what's in"],
}

def detect_transaction_type(query: str) -> str:
    q = query.lower()
    for action, keywords in TRANSACTION_KEYWORDS.items():
        if any(k in q for k in keywords):
            return action
    return "view"

def extract_product_from_query(query: str) -> list:
    """Search Vertex AI for products mentioned in the query"""
    # Remove transaction words to get the product description
    remove_words = ["add", "put", "place", "to cart", "to my cart",
                    "remove", "delete", "from cart", "please", "can you"]
    clean = query.lower()
    for w in remove_words:
        clean = clean.replace(w, "").strip()
    if not clean:
        return []
    results, _ = search_products(query=clean, page_size=3)
    return results

def log_cart_event(session_id, event_type, cart, risk_score,
                   hitl, sku_id="", promo="", discount=0.0):
    rows = [{
        "event_id":      str(uuid.uuid4()),
        "session_id":    session_id,
        "event_type":    event_type,
        "sku_id":        sku_id,
        "title":         "",
        "price":         0.0,
        "quantity":      1,
        "promo_code":    promo,
        "discount_pct":  discount,
        "cart_total":    cart.get("total", 0),
        "risk_score":    risk_score,
        "hitl_required": hitl,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "status":        "blocked" if hitl else "approved",
    }]
    try:
        bq.insert_rows_json("retail-ai-mvp.retail_mvp.cart_events", rows)
    except Exception as e:
        print(f"[Cart Log] BigQuery error: {e}")

def transaction_executor_node(state: GraphState) -> GraphState:
    """Transaction Executor — handles cart operations"""
    query      = state["query"]
    session_id = state["session_id"]
    products   = state.get("products", [])

    event_type   = detect_transaction_type(query)
    cart         = get_cart(session_id)
    risk_score   = 0.0
    hitl         = False
    discount_pct = 0.0
    response     = ""

    try:
        if event_type == "add":
            # If no products in state — search automatically
            if not products:
                products = extract_product_from_query(query)

            if not products:
                response = ("I couldn't find that product in our catalogue. "
                           "Please search for it first and then ask me to add it.")
            else:
                product = products[0]
                cart = add_item(session_id, product)
                risk_score, hitl, reasons = calculate_risk_score(cart, "add")
                if hitl:
                    response = (
                        f"Your order has been flagged for review. "
                        f"Risk factors: {', '.join(reasons)}. "
                        f"A team member will confirm shortly."
                    )
                else:
                    response = (
                        f"Added '{product['title']}' by {product['brand']} "
                        f"(Rs.{product['price']:.0f}) to your cart. "
                        f"Cart total: Rs.{cart['total']:.0f}."
                    )
                log_cart_event(session_id, "add", cart,
                               risk_score, hitl, product["sku_id"])

        elif event_type == "remove":
            if cart["items"]:
                sku_id = cart["items"][0]["sku_id"]
                title  = cart["items"][0]["title"]
                cart   = remove_item(session_id, sku_id)
                response = (f"Removed '{title}' from cart. "
                           f"Cart total: Rs.{cart['total']:.0f}.")
            else:
                response = "Your cart is already empty."
            risk_score, hitl, _ = calculate_risk_score(cart, "remove")
            log_cart_event(session_id, "remove", cart, risk_score, hitl)

        elif event_type == "promo":
            promo_codes = ["SAVE10", "SAVE20", "SAVE30", "WELCOME"]
            words = query.upper().split()
            code  = next((w for w in words if w in promo_codes), None)
            if code:
                cart, discount_pct = apply_promo(session_id, code)
                risk_score, hitl, reasons = calculate_risk_score(
                    cart, "promo", discount_pct)
                if hitl:
                    response = (
                        f"Promo {code} ({discount_pct}% off) flagged for review. "
                        f"Reason: {', '.join(reasons)}."
                    )
                else:
                    response = (
                        f"Promo code {code} applied! {discount_pct}% discount. "
                        f"New cart total: Rs.{cart['total']:.0f}."
                    )
                log_cart_event(session_id, "promo", cart, risk_score,
                               hitl, promo=code, discount=discount_pct)
            else:
                response = ("Please provide a valid promo code. "
                           "Available: SAVE10, SAVE20, SAVE30, WELCOME.")

        elif event_type == "checkout":
            if not cart["items"]:
                response = "Your cart is empty. Add products before checking out."
            else:
                risk_score, hitl, reasons = calculate_risk_score(
                    cart, "checkout", cart.get("discount_pct", 0))
                if hitl:
                    response = (
                        f"Your order of Rs.{cart['total']:.0f} has been "
                        f"flagged for review. Reason: {', '.join(reasons)}. "
                        f"A team member will contact you shortly."
                    )
                else:
                    response = (
                        f"Order confirmed! Total: Rs.{cart['total']:.0f}. "
                        f"Delivery in 3-5 business days. Thank you!"
                    )
                    notify_order_confirmed(session_id, cart['total'])
                log_cart_event(session_id, "checkout", cart, risk_score, hitl)

        else:  # view cart
            if cart["items"]:
                items_text = "\n".join([
                    f"- {i['title']} x{i['quantity']} = Rs.{i['price']*i['quantity']:.0f}"
                    for i in cart["items"]
                ])
                response = (f"Your cart:\n{items_text}\n"
                           f"Total: Rs.{cart['total']:.0f}")
            else:
                response = "Your cart is empty. Search for products to add."

    except Exception as e:
        response = "I could not process that cart action. Please try again."
        print(f"[Transaction Executor] Error: {e}")

    return {
        **state,
        "response":      response,
        "intent":        "transact",
        "products":      products,
        "hitl_required": hitl,
        "risk_score":    risk_score,
    }
