import os
from dotenv import load_dotenv
load_dotenv()

PROJECT_ID    = os.getenv("GCP_PROJECT_ID", "retail-ai-mvp")
LOCATION      = os.getenv("GCP_LOCATION", "global")
ENGINE_ID     = os.getenv("VERTEX_SEARCH_ENGINE_ID", "retail-search-app_1778633921898")
DATA_STORE_ID = os.getenv("VERTEX_SEARCH_DATASTORE_ID", "retail-catalog-store_1778632083248")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL  = "gemini-2.5-flash"
BQ_DATASET    = "retail_mvp"
BQ_TABLE      = "catalog_dim"
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "retail-ai-mvp-secret-2026")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL", "nadeem.ahmad.arch@gmail.com")
