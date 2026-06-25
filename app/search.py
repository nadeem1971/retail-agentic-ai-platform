from google.cloud import discoveryengine_v1 as discoveryengine
from google.cloud import bigquery
from app.config import PROJECT_ID, LOCATION, ENGINE_ID, BQ_DATASET
import functools, time

bq_client = bigquery.Client(project=PROJECT_ID)

@functools.lru_cache(maxsize=256)
def _cached_search(query: str, page_size: int = 10):
    client = discoveryengine.SearchServiceClient()
    serving_config = (
        f"projects/{PROJECT_ID}/locations/{LOCATION}"
        f"/collections/default_collection"
        f"/engines/{ENGINE_ID}"
        f"/servingConfigs/default_config"
    )
    request = discoveryengine.SearchRequest(
        serving_config=serving_config,
        query=query,
        page_size=page_size,
    )
    response = client.search(request)
    results = []
    for r in response.results:
        doc = dict(r.document.struct_data)
        results.append({
            "sku_id":          doc.get("sku_id", ""),
            "title":           doc.get("title", ""),
            "description":     doc.get("description", ""),
            "category":        doc.get("category", ""),
            "price":           float(doc.get("price", 0)),
            "inventory_count": int(doc.get("inventory_count", 0)),
            "brand":           doc.get("brand", ""),
        })
    return results

def search_products(query: str, page_size: int = 10):
    start = time.time()
    results = _cached_search(query, page_size)
    # GUARDRAIL G1: Remove out-of-stock products
    in_stock = [r for r in results if r["inventory_count"] > 0]
    latency_ms = int((time.time() - start) * 1000)
    return in_stock, latency_ms

def log_search(session_id, query, results_count, latency_ms, dlp_triggered=False):
    from datetime import datetime, timezone
    rows = [{
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "session_id":    session_id,
        "query":         query,
        "results_count": results_count,
        "latency_ms":    latency_ms,
        "dlp_triggered": dlp_triggered,
    }]
    table_ref = f"{PROJECT_ID}.{BQ_DATASET}.search_logs"
    errors = bq_client.insert_rows_json(table_ref, rows)
    if errors:
        print(f"BigQuery logging error: {errors}")
