from app.agents.state import GraphState
from app.config import PROJECT_ID
from google.cloud import firestore
from datetime import datetime, timezone
import uuid

db = firestore.Client(project=PROJECT_ID, database="default")

BANNED_TOPICS = [
    "competitor", "amazon", "flipkart", "myntra",
    "fake", "counterfeit", "stolen", "illegal",
]

def check_violations(query: str, response: str) -> tuple:
    violations = []
    q = query.lower()
    for topic in BANNED_TOPICS:
        if topic in q:
            violations.append(f"Banned topic: {topic}")
    return len(violations) > 0, violations

def queue_hitl(session_id, event_id, query, response, risk_score, reasons):
    db.collection("hitl_queue").document(event_id).set({
        "event_id":   event_id,
        "session_id": session_id,
        "query":      query,
        "response":   response,
        "risk_score": risk_score,
        "reasons":    reasons,
        "status":     "pending",
        "created_at": datetime.now(timezone.utc),
    })
    print(f"[Policy Watcher] HITL queued: {event_id} | risk: {risk_score}")

def policy_watcher_node(state: GraphState) -> GraphState:
    from app.agents.mcp_notifier import notify_hitl_raised

    query      = state["query"]
    response   = state.get("response", "")
    session_id = state["session_id"]
    risk_score = state.get("risk_score", 0.0)
    hitl       = state.get("hitl_required", False)

    # Check policy violations
    violated, violations = check_violations(query, response)
    if violated:
        return {**state,
            "response": "I'm sorry, I cannot process that request. Please contact our support team.",
            "hitl_required": True,
            "hitl_reasons": violations
        }

    # Queue HITL for high-risk transactions
    if hitl and risk_score >= 0.8:
        event_id = str(uuid.uuid4())
        reasons  = state.get("hitl_reasons", [f"Risk score: {risk_score:.2f}"])
        queue_hitl(session_id, event_id, query, response, risk_score, reasons)
        notify_hitl_raised(session_id, event_id, risk_score)
        return {**state,
            "response": (
                f"{response}\n\n"
                f"⚠️ This transaction has been flagged for review "
                f"(risk score: {risk_score:.2f}). "
                f"A team member will confirm within 2 hours."
            ),
            "hitl_event_id": event_id
        }

    return state
