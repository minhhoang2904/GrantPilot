"""Environment-only configuration for Server C."""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent

try:
    from dotenv import load_dotenv

    load_dotenv(BASE_DIR / ".env")
    load_dotenv(PROJECT_DIR / ".env")
except ImportError:
    pass

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE", os.getenv("MONGODB_DB", "grantpilot")
).strip()
MONGODB_POLICIES_COLLECTION = os.getenv("MONGODB_POLICIES_COLLECTION", "policies").strip()
MONGODB_LEGAL_UNITS_COLLECTION = os.getenv(
    "MONGODB_LEGAL_UNITS_COLLECTION", "legal_units"
).strip()
MONGODB_DOCUMENTS_COLLECTION = os.getenv(
    "MONGODB_DOCUMENTS_COLLECTION", "legal_documents"
).strip()
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "5000"))
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
)

FPT_BASE_URL = os.getenv("FPT_BASE_URL", "https://mkp-api.fptcloud.com").rstrip("/")
FPT_API_KEY = os.getenv("FPT_API_KEY", "").strip()
FPT_ELIGIBILITY_MODEL = os.getenv("FPT_ELIGIBILITY_MODEL", "GLM-5.2").strip()
FPT_ELIGIBILITY_MAX_TOKENS = int(os.getenv("FPT_ELIGIBILITY_MAX_TOKENS", "1200"))
FPT_TIMEOUT_SECONDS = float(os.getenv("FPT_TIMEOUT_SECONDS", "60"))
ELIGIBILITY_LLM_ENABLED = os.getenv("ELIGIBILITY_LLM_ENABLED", "true").lower() in {
    "1", "true", "yes",
}

DEFAULT_TOP_K = int(os.getenv("ELIGIBILITY_TOP_K", "10"))
MAX_TOP_K = int(os.getenv("ELIGIBILITY_MAX_TOP_K", "50"))
STRICT_LEGAL_STATUS = os.getenv("STRICT_LEGAL_STATUS", "false").lower() in {
    "1", "true", "yes",
}


def mongodb_enabled() -> bool:
    return bool(MONGODB_URI and MONGODB_DATABASE)


def llm_enabled() -> bool:
    return bool(ELIGIBILITY_LLM_ENABLED and FPT_API_KEY and FPT_ELIGIBILITY_MODEL)
