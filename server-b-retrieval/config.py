"""Cau hinh tap trung cho Server B.

Khong co secret nao duoc ghi trong source. MongoDB, Pinecone, Redis va FPT deu
duoc bat/tat bang bien moi truong; vi vay test offline khong can credential that.
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

# Production dung MongoDB lam canonical store. JSONL chi la fallback cho test,
# local development hoac migration; khong nam tren production request path.
LEGAL_DATA_BACKEND = os.getenv("LEGAL_DATA_BACKEND", "mongodb").strip().lower()
if LEGAL_DATA_BACKEND not in {"mongodb", "jsonl"}:
    raise ValueError("LEGAL_DATA_BACKEND phai la 'mongodb' hoac 'jsonl'")

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

# Pinecone: ung dung chi query index da duoc Server A tao/upsert, tuyet doi
# khong tu tao hay xoa index luc startup. Host duoc uu tien trong production de
# tranh describe-index network call; name la fallback tien loi khi dev.
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "").strip()
PINECONE_INDEX_HOST = os.getenv("PINECONE_INDEX_HOST", "").strip()
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "").strip()
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "legal_units").strip()

# FPT: query embedding phai cung model voi vector Server A da upsert.
FPT_BASE_URL = os.getenv("FPT_BASE_URL", "https://mkp-api.fptcloud.com").rstrip("/")
FPT_API_KEY = os.getenv("FPT_API_KEY", "").strip()
FPT_EMBEDDING_MODEL = os.getenv("FPT_EMBEDDING_MODEL", "Vietnamese_Embedding")
FPT_RERANK_MODEL = os.getenv("FPT_RERANK_MODEL", "bge-reranker-v2-m3")
# Tach model theo nhiem vu: rewrite can nhanh/re, answer can chat luong. Bien
# FPT_LLM_MODEL cu van duoc dung lam fallback de khong pha config dang co.
_LEGACY_LLM_MODEL = os.getenv("FPT_LLM_MODEL", "").strip()
FPT_QUERY_REWRITE_MODEL = os.getenv(
    "FPT_QUERY_REWRITE_MODEL", "DeepSeek-V4-Flash"
).strip()
FPT_ANSWER_MODEL = os.getenv("FPT_ANSWER_MODEL", _LEGACY_LLM_MODEL or "GLM-5.2").strip()
FPT_ADVISORY_MODEL = os.getenv("FPT_ADVISORY_MODEL", FPT_ANSWER_MODEL).strip()
FPT_QUERY_REWRITE_MAX_TOKENS = int(os.getenv("FPT_QUERY_REWRITE_MAX_TOKENS", "512"))
FPT_ANSWER_MAX_TOKENS = int(os.getenv("FPT_ANSWER_MAX_TOKENS", "8192"))
FPT_ADVISORY_MAX_TOKENS = int(os.getenv("FPT_ADVISORY_MAX_TOKENS", "1600"))
FPT_ADVISORY_ENABLED = os.getenv("FPT_ADVISORY_ENABLED", "true").strip().lower() in {
    "1", "true", "yes", "on",
}

# Grounded RAG answer khong can agentic/long-horizon reasoning. Tat thinking de
# tranh GLM dung het completion budget cho reasoning_content ma content rong.
# Neu FPT proxy chua ho tro hai field nay, client se retry mot lan khi gap 400/422.
FPT_ANSWER_THINKING = os.getenv("FPT_ANSWER_THINKING", "disabled").strip().lower()
FPT_ANSWER_REASONING_EFFORT = os.getenv(
    "FPT_ANSWER_REASONING_EFFORT", "none"
).strip().lower()
FPT_EMBEDDINGS_URL = os.getenv("FPT_EMBEDDINGS_URL", f"{FPT_BASE_URL}/embeddings")
FPT_RERANK_URL = os.getenv("FPT_RERANK_URL", f"{FPT_BASE_URL}/v1/rerank")
FPT_CHAT_URL = os.getenv("FPT_CHAT_URL", f"{FPT_BASE_URL}/chat/completions")
FPT_TIMEOUT_SECONDS = float(os.getenv("FPT_TIMEOUT_SECONDS", "60"))

# Redis chi luu recent conversation state cho query rewrite. Khong co URL thi
# tu dong dung memory trong RAM de local dev van chay duoc.
REDIS_URL = os.getenv("REDIS_URL", "").strip()
CHAT_MEMORY_TTL_SECONDS = int(os.getenv("CHAT_MEMORY_TTL_SECONDS", "86400"))
CHAT_HISTORY_MESSAGES = int(os.getenv("CHAT_HISTORY_MESSAGES", "8"))
CHAT_STORED_MESSAGES = int(os.getenv("CHAT_STORED_MESSAGES", "20"))

# Server C is called only in advisory mode. Lookup mode remains available when
# Server C is down because it is a separate retrieval-only pipeline.
SERVER_C_URL = os.getenv("SERVER_C_URL", "http://server-c-eligibility:8002").rstrip("/")
SERVER_C_TIMEOUT_SECONDS = float(os.getenv("SERVER_C_TIMEOUT_SECONDS", "30"))

# Retrieval defaults. Threshold reranker mac dinh tat (-1) vi moi model co
# thang diem khac nhau; phai tune bang benchmark roi moi bat.
DENSE_TOP_K = int(os.getenv("DENSE_TOP_K", "20"))
BM25_TOP_K = int(os.getenv("BM25_TOP_K", "20"))
FUSION_TOP_K = int(os.getenv("FUSION_TOP_K", "30"))
RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))
MAX_RESULTS_PER_ARTICLE = int(os.getenv("MAX_RESULTS_PER_ARTICLE", "3"))
RERANK_MIN_SCORE = float(os.getenv("RERANK_MIN_SCORE", "-1"))


def pinecone_enabled() -> bool:
    return bool(PINECONE_API_KEY and (PINECONE_INDEX_HOST or PINECONE_INDEX_NAME))


def fpt_enabled() -> bool:
    return bool(FPT_API_KEY)


def mongodb_enabled() -> bool:
    return bool(MONGODB_URI and MONGODB_DATABASE and MONGODB_LEGAL_UNITS_COLLECTION)


def legal_data_configured() -> bool:
    if LEGAL_DATA_BACKEND == "mongodb":
        return mongodb_enabled()
    return LEGAL_UNITS_PATH.exists()
