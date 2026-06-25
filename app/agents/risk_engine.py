def calculate_risk_score(
    cart: dict,
    event_type: str,
    discount_pct: float = 0.0
) -> tuple:
    """
    Calculate risk score for cart action.
    Returns (risk_score, reasons)
    
    Risk factors:
    - Cart total > 10,000 = high value order
    - Discount > 20% = large discount
    - Quantity > 5 of same item = bulk order
    - Checkout with promo + high value = combined risk
    """
    risk = 0.0
    reasons = []

    cart_total = cart.get("total", 0)
    items      = cart.get("items", [])

    # Factor 1 — High cart value
    if cart_total > 10000:
        risk += 0.4
        reasons.append(f"High cart value: Rs.{cart_total:.0f}")
    elif cart_total > 5000:
        risk += 0.2
        reasons.append(f"Medium cart value: Rs.{cart_total:.0f}")

    # Factor 2 — Large discount
    if discount_pct > 20:
        risk += 0.4
        reasons.append(f"Large discount: {discount_pct}%")
    elif discount_pct > 10:
        risk += 0.2
        reasons.append(f"Moderate discount: {discount_pct}%")

    # Factor 3 — Bulk order
    for item in items:
        if item.get("quantity", 1) > 5:
            risk += 0.3
            reasons.append(f"Bulk order: {item['quantity']}x {item['title']}")

    # Factor 4 — Checkout with combined risk
    if event_type == "checkout" and discount_pct > 0 and cart_total > 5000:
        risk += 0.2
        reasons.append("Checkout with promo on high-value cart")

    # Cap at 1.0
    risk = min(round(risk, 2), 1.0)
    hitl = risk >= 0.8

    return risk, hitl, reasons