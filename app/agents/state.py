from typing import TypedDict, Optional, List

class GraphState(TypedDict):
    query:              str
    intent:             str
    products:           list
    response:           str
    session_id:         str
    history:            list
    latency_ms:         int
    error:              Optional[str]
    hitl_required:      Optional[bool]
    risk_score:         Optional[float]
    hitl_reasons:       Optional[List[str]]
    hitl_event_id:      Optional[str]
    rag_chunks_used:    Optional[int]
