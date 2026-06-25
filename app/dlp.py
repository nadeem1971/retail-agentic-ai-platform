from google.cloud import dlp_v2
from app.config import PROJECT_ID

dlp_client = dlp_v2.DlpServiceClient()

INFO_TYPES = [
    {"name": "EMAIL_ADDRESS"},
    {"name": "PHONE_NUMBER"},
    {"name": "CREDIT_CARD_NUMBER"},
    {"name": "INDIA_AADHAAR_INDIVIDUAL"},
]

def scan_and_redact(text: str) -> tuple:
    if not text or len(text.strip()) == 0:
        return text, False
    parent = f"projects/{PROJECT_ID}/locations/global"
    item = {"value": text}
    inspect_config = {
        "info_types": INFO_TYPES,
        "min_likelihood": dlp_v2.Likelihood.LIKELY,
    }
    deidentify_config = {
        "info_type_transformations": {
            "transformations": [{
                "primitive_transformation": {
                    "replace_with_info_type_config": {}
                }
            }]
        }
    }
    try:
        response = dlp_client.deidentify_content(
            request={
                "parent":            parent,
                "deidentify_config": deidentify_config,
                "inspect_config":    inspect_config,
                "item":              item,
            }
        )
        cleaned  = response.item.value
        pii_found = cleaned != text
        return cleaned, pii_found
    except Exception as e:
        print(f"DLP error: {e}")
        return text, False
