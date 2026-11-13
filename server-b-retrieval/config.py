"""Cau hinh tap trung cho Server B.

Khong co secret nao duoc ghi trong source. MongoDB, Pinecone, Redis va LLM deu
duoc bat/tat bang bien moi truong; vi vay test offline khong can credential that.

Multi-provider: moi nhiem vu (embed, rerank, rewrite, answer) co the dung
provider rieng (Jina, Groq, Mistral, ...). Bien FPT_* cu van duoc dung lam
fallback de khong pha config dang co.
"""

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

# ---------------------------------------------------------------------------
# Legal data backend
# ---------------------------------------------------------------------------
LEGAL_DATA_BACKEND = os.getenv("LEGAL_DATA_BACKEND", "mongodb").strip().lower()
if LEGAL_DATA_BACKEND not in {"mongodb", "jsonl"}:
    raise ValueError("LEGAL_DATA_BACKEND phai la 'mongodb' hoac 'jsonl'")

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "grantpilot").strip()
MONGODB_DOCUMENTS_COLLECTION = os.getenv(
    "MONGODB_DOCUMENTS_COLLECTION", "legal_documents"
).strip()
MONGODB_LEGAL_UNITS_COLLECTION = os.getenv(
    "MONGODB_LEGAL_UNITS_COLLECTION", "legal_units"
).strip()
MONGODB_POLICIES_COLLECTION = os.getenv(
    "MONGODB_POLICIES_COLLECTION", "policies"
).strip()
MONGODB_CONNECT_TIMEOUT_MS = int(os.getenv("MONGODB_CONNECT_TIMEOUT_MS", "5000"))
MONGODB_SERVER_SELECTION_TIMEOUT_MS = int(
    os.getenv("MONGODB_SERVER_SELECTION_TIMEOUT_MS", "5000")
)

# Fallback JSONL cu de offline test/recovery.
LEGAL_UNITS_PATH = Path(
    os.getenv(
        "LEGAL_UNITS_PATH",
        PROJECT_DIR / "server-a-ingestion" / "data" / "processed" / "legal_units.jsonl",
    )
)
POLICIES_PATH = Path(
    os.getenv(
        "POLICIES_PATH",
        PROJECT_DIR / "server-a-ingestion" / "data" / "policies.json",
    )
)
POLICY_DISCOVERY_PATH = Path(
    os.getenv(
        "POLICY_DISCOVERY_PATH",
        PROJECT_DIR / "server-a-ingestion" / "data" / "golden_policies_mvp.json",
    )
)

# ---------------------------------------------------------------------------
# Pinecone
# ---------------------------------------------------------------------------
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX_HOST = os.getenv("PINECONE_INDEX_HOST", "").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "").strip()
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "legal_units").strip()

# ---------------------------------------------------------------------------
# LLM / Embedding / Rerank — multi-provider config
#
# Each role (embed, rerank, rewrite, answer, advisory) reads its own
# _API_KEY, _BASE_URL, and _MODEL. Missing values fall back to the legacy
# FPT_* variables so existing deployments keep working.
# ---------------------------------------------------------------------------
_FPT_BASE_URL = os.getenv("FPT_BASE_URL", "").strip().rstrip("/")
_FPT_API_KEY = os.getenv("FPT_API_KEY", "").strip()

# -- Embeddings (default: Jina AI) -----------------------------------------
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY", _FPT_API_KEY).strip()
EMBEDDING_BASE_URL = os.getenv(
    "EMBEDDING_BASE_URL",
    _FPT_BASE_URL or "https://api.jina.ai/v1",
).strip().rstrip("/")
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    os.getenv("FPT_EMBEDDING_MODEL", "jina-embeddings-v3"),
).strip()
EMBEDDING_URL = os.getenv(
    "EMBEDDING_URL",
    os.getenv("FPT_EMBEDDINGS_URL", f"{EMBEDDING_BASE_URL}/embeddings"),
).strip()

# -- Reranker (default: Jina AI) -------------------------------------------
RERANK_API_KEY = os.getenv("RERANK_API_KEY", EMBEDDING_API_KEY).strip()
RERANK_BASE_URL = os.getenv(
    "RERANK_BASE_URL",
    EMBEDDING_BASE_URL,
).strip().rstrip("/")
RERANK_MODEL = os.getenv(
    "RERANK_MODEL",
    os.getenv("FPT_RERANK_MODEL", "jina-reranker-v2-base-multilingual"),
).strip()
RERANK_URL = os.getenv(
    "RERANK_URL",
    os.getenv("FPT_RERANK_URL", f"{RERANK_BASE_URL}/rerank"),
).strip()

# -- Query-rewrite LLM (default: Groq) ------------------------------------
REWRITE_API_KEY = os.getenv("REWRITE_API_KEY", _FPT_API_KEY).strip()
REWRITE_BASE_URL = os.getenv(
    "REWRITE_BASE_URL",
    _FPT_BASE_URL or "https://api.groq.com/openai/v1",
).strip().rstrip("/")
REWRITE_MODEL = os.getenv(
    "REWRITE_MODEL",
    os.getenv("FPT_QUERY_REWRITE_MODEL", "openai/gpt-oss-120b"),
).strip()
REWRITE_CHAT_URL = os.getenv(
    "REWRITE_CHAT_URL",
    f"{REWRITE_BASE_URL}/chat/completions",
).strip()
REWRITE_MAX_TOKENS = int(
    os.getenv("REWRITE_MAX_TOKENS", os.getenv("FPT_QUERY_REWRITE_MAX_TOKENS", "2048"))
)

# -- Answer LLM (default: Groq) -------------------------------------------
ANSWER_API_KEY = os.getenv("ANSWER_API_KEY", _FPT_API_KEY).strip()
ANSWER_BASE_URL = os.getenv(
    "ANSWER_BASE_URL",
    _FPT_BASE_URL or "https://api.groq.com/openai/v1",
).strip().rstrip("/")
ANSWER_MODEL = os.getenv(
    "ANSWER_MODEL",
    os.getenv("FPT_ANSWER_MODEL", "openai/gpt-oss-120b"),
).strip()
ANSWER_CHAT_URL = os.getenv(
    "ANSWER_CHAT_URL",
    os.getenv("FPT_CHAT_URL", f"{ANSWER_BASE_URL}/chat/completions"),
).strip()
ANSWER_MAX_TOKENS = int(
    os.getenv("ANSWER_MAX_TOKENS", os.getenv("FPT_ANSWER_MAX_TOKENS", "8192"))
)

# -- Advisory LLM (defaults to answer provider) ----------------------------
ADVISORY_API_KEY = os.getenv("ADVISORY_API_KEY", ANSWER_API_KEY).strip()
ADVISORY_BASE_URL = os.getenv(
    "ADVISORY_BASE_URL", ANSWER_BASE_URL
).strip().rstrip("/")
ADVISORY_MODEL = os.getenv(
    "ADVISORY_MODEL",
    os.getenv("FPT_ADVISORY_MODEL", ANSWER_MODEL),
).strip()
ADVISORY_CHAT_URL = os.getenv(
    "ADVISORY_CHAT_URL",
    f"{ADVISORY_BASE_URL}/chat/completions",
).strip()
ADVISORY_MAX_TOKENS = int(
    os.getenv("ADVISORY_MAX_TOKENS", os.getenv("FPT_ADVISORY_MAX_TOKENS", "4096"))
)
ADVISORY_ENABLED = os.getenv(
    "ADVISORY_ENABLED",
    os.getenv("FPT_ADVISORY_ENABLED", "true"),
).strip().lower() in {"1", "true", "yes", "on"}

# -- Shared LLM settings --------------------------------------------------
LLM_TIMEOUT_SECONDS = float(
    os.getenv("LLM_TIMEOUT_SECONDS", os.getenv("FPT_TIMEOUT_SECONDS", "60"))
)

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "").strip()
CHAT_MEMORY_TTL_SECONDS = int(os.getenv("CHAT_MEMORY_TTL_SECONDS", "86400"))
CHAT_HISTORY_MESSAGES = int(os.getenv("CHAT_HISTORY_MESSAGES", "8"))
CHAT_STORED_MESSAGES = int(os.getenv("CHAT_STORED_MESSAGES", "20"))

# ---------------------------------------------------------------------------
# Server C
# ---------------------------------------------------------------------------
SERVER_C_URL = os.getenv("SERVER_C_URL", "http://localhost:8002").rstrip("/")
SERVER_C_TIMEOUT_SECONDS = float(os.getenv("SERVER_C_TIMEOUT_SECONDS", "30"))

# ---------------------------------------------------------------------------
# Retrieval tuning
# ---------------------------------------------------------------------------
DENSE_TOP_K = int(os.getenv("DENSE_TOP_K", "20"))
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "20"))
FUSION_TOP_K = int(os.getenv("FUSION_TOP_K", "30"))
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))
MAX_RESULTS_PER_ARTICLE = int(os.getenv("MAX_RESULTS_PER_ARTICLE", "3"))
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "-1"))


# ---------------------------------------------------------------------------
# Feature flags
# ---------------------------------------------------------------------------
def pinecone_enabled() -> bool:
    return bool(PINECONE_API_KEY and (PINECONE_INDEX_HOST or PINECONE_INDEX_NAME))


def embedding_enabled() -> bool:
    return bool(EMBEDDING_API_KEY)


def rewrite_enabled() -> bool:
    return bool(REWRITE_API_KEY and REWRITE_MODEL)


def answer_enabled() -> bool:
    return bool(ANSWER_API_KEY and ANSWER_MODEL)


def mongodb_enabled() -> bool:
    return bool(MONGODB_URI and MONGODB_DATABASE and MONGODB_LEGAL_UNITS_COLLECTION)


def legal_data_configured() -> bool:
    if LEGAL_DATA_BACKEND == "mongodb":
        return mongodb_enabled()
    return LEGAL_UNITS_PATH.exists()
