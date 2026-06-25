from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from app.auth import verify_api_key
from app.search import search_products, log_search
from app.chat import chat
import uuid
from google.cloud import firestore as fs_client

app = FastAPI(
    title="Retail AI Platform API",
    description="AI-powered product discovery — Vertex AI Search + Gemini + BigQuery",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class SearchRequest(BaseModel):
    query:      str
    page_size:  Optional[int] = 10
    session_id: Optional[str] = None

class ChatRequest(BaseModel):
    query:      str
    session_id: Optional[str] = None

@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0", "project": "retail-ai-mvp"}

@app.post("/search")
async def search(
    request: SearchRequest,
    api_key: str = Depends(verify_api_key)
):
    session_id = request.session_id or str(uuid.uuid4())
    try:
        results, latency_ms = search_products(
            query=request.query,
            page_size=request.page_size
        )
        log_search(
            session_id=session_id,
            query=request.query,
            results_count=len(results),
            latency_ms=latency_ms
        )
        return {
            "session_id":  session_id,
            "query":       request.query,
            "results":     results,
            "total_found": len(results),
            "latency_ms":  latency_ms,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat_endpoint(
    request: ChatRequest,
    api_key: str = Depends(verify_api_key)
):
    import time
    from app.agents.graph import retail_graph
    from app.chat import get_session, save_session
    from google.cloud import firestore as fs

    session_id = request.session_id or str(uuid.uuid4())
    start = time.time()

    try:
        history = get_session(session_id)
        initial_state = {
            "query":      request.query,
            "intent":     "",
            "products":   [],
            "response":   "",
            "session_id": session_id,
            "history":    history,
            "latency_ms": 0,
            "error":      None,
        }

        # Run through LangGraph
        result = retail_graph.invoke(initial_state)

        # Save session
        history.append({"role": "user",      "content": request.query})
        history.append({"role": "assistant", "content": result["response"]})
        save_session(session_id, history)

        # Log to BigQuery
        log_search(
            session_id=session_id,
            query=request.query,
            results_count=len(result.get("products", [])),
            latency_ms=int((time.time() - start) * 1000),
            dlp_triggered=False
        )

        return {
            "session_id":    session_id,
            "intent":        result["intent"],
            "response":      result["response"],
            "products":      result.get("products", []),
            "hitl_required": result.get("hitl_required", False),
            "risk_score":    result.get("risk_score", 0.0),
            "latency_ms":    int((time.time() - start) * 1000),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@app.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    api_key: str = Depends(verify_api_key)
):
    """GDPR right to erasure — deletes customer session data"""
    try:
        db = fs_client.Client(
            project="retail-ai-mvp",
            database="default"
        )
        db.collection("sessions").document(session_id).delete()
        log_search(
            session_id=session_id,
            query="[GDPR_ERASURE_REQUEST]",
            results_count=0,
            latency_ms=0,
            dlp_triggered=False
        )
        return {
            "deleted":    True,
            "session_id": session_id,
            "message":    "Session data permanently deleted per GDPR right to erasure"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/hitl/queue")
async def get_hitl_queue(api_key: str = Depends(verify_api_key)):
    from app.chat import db
    docs = db.collection("hitl_queue").where("status","==","pending").stream()
    items = [doc.to_dict() for doc in docs]
    return {"pending": items, "count": len(items)}

@app.post("/hitl/approve/{event_id}")
async def approve_hitl(event_id: str, api_key: str = Depends(verify_api_key)):
    from app.chat import db
    from datetime import datetime, timezone
    db.collection("hitl_queue").document(event_id).update({
        "status": "approved",
        "approved_at": datetime.now(timezone.utc)
    })
    return {"event_id": event_id, "status": "approved"}

@app.post("/hitl/reject/{event_id}")
async def reject_hitl(event_id: str, api_key: str = Depends(verify_api_key)):
    from app.chat import db
    from datetime import datetime, timezone
    db.collection("hitl_queue").document(event_id).update({
        "status": "rejected",
        "rejected_at": datetime.now(timezone.utc)
    })
    return {"event_id": event_id, "status": "rejected"}