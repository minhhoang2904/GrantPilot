"""Multi-provider LLM clients cho embedding, rerank, rewrite, answer.

Moi nhiem vu co the dung provider rieng (Jina, Groq, Mistral, ...)
voi API key va base URL doc lap. Tat ca deu dung OpenAI-compatible format.
"""

from __future__ import annotations

import json
import re
from typing import Any

import config


class LLMClient:
    """Unified client that routes each operation to its configured provider."""

    def __init__(self, *, embedding_api_key: str | None = None) -> None:
        self._embedding_api_key = (
            embedding_api_key if embedding_api_key is not None
            else config.EMBEDDING_API_KEY
        ).strip()

    @property
    def enabled(self) -> bool:
        return bool(self._embedding_api_key or config.ANSWER_API_KEY)

    @staticmethod
    def _post(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not api_key:
            raise RuntimeError("Chua cau hinh API key cho provider")
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("Thieu package httpx") from exc
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GrandPilot-Retrieval/2.0",
        }
        with httpx.Client(timeout=config.LLM_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    # -- Embeddings (Jina AI) -----------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post(
            config.EMBEDDING_URL,
            config.EMBEDDING_API_KEY,
            {
                "model": config.EMBEDDING_MODEL,
                "input": texts,
                "encoding_format": "float",
            },
        )
        rows = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        if len(rows) != len(texts):
            raise RuntimeError(f"Embedding API tra {len(rows)}/{len(texts)} vectors")
        return [row["embedding"] for row in rows]

    # -- Reranker (Jina AI) -------------------------------------------------

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        data = self._post(
            config.RERANK_URL,
            config.RERANK_API_KEY,
            {
                "model": config.RERANK_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
        )
        return [
            (int(item["index"]), float(item.get("relevance_score", item.get("score", 0.0))))
            for item in data.get("results", [])
        ]

    # -- Query rewrite (Groq) -----------------------------------------------

    def rewrite_query(self, question: str, history: list[dict[str, str]]) -> str:
        if not config.rewrite_enabled() or not history:
            return _deterministic_rewrite(question, history)
        prior = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        data = self._post(
            config.REWRITE_CHAT_URL,
            config.REWRITE_API_KEY,
            {
                "model": config.REWRITE_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Viết lại câu hỏi hiện tại thành một câu hỏi độc lập để tra cứu "
                            "văn bản pháp luật Việt Nam. Chỉ dùng thông tin trong lịch sử, "
                            "không trả lời, không thêm điều luật hay con số. Chỉ xuất câu hỏi."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Lịch sử:\n{prior}\n\nCâu hiện tại: {question}",
                    },
                ],
                "temperature": 0,
                "max_tokens": config.REWRITE_MAX_TOKENS,
                "stream": False,
            },
        )
        content = data["choices"][0]["message"].get("content") or ""
        return content.strip() or _deterministic_rewrite(question, history)

    # -- Grounded answer (Groq / Mistral) -----------------------------------

    def answer(self, question: str, evidence: list[dict], language: str = "vi") -> str | None:
        if not config.answer_enabled() or not evidence:
            return None
        ANSWER_SYSTEM = {
            "vi": (
                "Bạn là trợ lý tra cứu pháp luật. Chỉ trả lời bằng bằng chứng "
                "được cung cấp. Mỗi khẳng định pháp lý phải dẫn số văn bản và "
                "Điều/Khoản/Điểm. Nếu bằng chứng không đủ, nói rõ là không đủ. "
                "Không tự kết luận doanh nghiệp chắc chắn đủ điều kiện. "
                "Viết văn bản thuần, không dùng Markdown (không **, #, bảng); dùng gạch "
                "đầu dòng '-' khi cần. Không in mã định danh trong ngoặc vuông."
            ),
            "en": (
                "You are a legal research assistant. Only answer using the provided evidence. "
                "Every legal claim must cite the document number and Article/Clause/Point. "
                "If evidence is insufficient, say so clearly. "
                "Do not conclude that a business definitely qualifies for support. "
                "The evidence is in Vietnamese; always write your answer in English. "
                "Write plain text without Markdown (no **, #, tables); use '-' bullets "
                "when needed. Do not print the bracketed identifiers."
            ),
        }
        lang = language if language in ANSWER_SYSTEM else "vi"
        blocks = []
        for unit in evidence:
            location = f"{unit.get('document_number', '')}, Điều {unit.get('article', '')}"
            if unit.get("clause"):
                location += f", khoản {unit['clause']}"
            if unit.get("point"):
                location += f", điểm {unit['point']}"
            blocks.append(f"[{unit['unit_id']}] {location}\n{unit.get('text', '')}")
        evidence_text = "\n\n".join(blocks)
        payload: dict[str, Any] = {
            "model": config.ANSWER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": ANSWER_SYSTEM[lang],
                },
                {
                    "role": "user",
                    "content": f"Bằng chứng:\n\n{evidence_text}\n\nCâu hỏi: {question}",
                },
            ],
            "temperature": 0,
            "max_tokens": config.ANSWER_MAX_TOKENS,
            "stream": False,
        }
        data = self._post(config.ANSWER_CHAT_URL, config.ANSWER_API_KEY, payload)
        choice = data.get("choices", [{}])[0]
        message = choice.get("message") or {}
        content = (message.get("content") or "").strip()
        if content:
            return content
        finish_reason = choice.get("finish_reason", "unknown")
        raise RuntimeError(
            "LLM trả content rỗng "
            f"(model={config.ANSWER_MODEL}, finish_reason={finish_reason}, "
            f"max_tokens={config.ANSWER_MAX_TOKENS})"
        )

    # -- Advisory suggestions (Groq / Mistral) ------------------------------

    def advise(self, advisory_payload: dict[str, Any], language: str = "vi") -> str | None:
        if not config.ADVISORY_ENABLED or not config.ADVISORY_MODEL:
            return None
        ADVISE_SYSTEM = {
            "vi": (
                "Bạn là chuyên viên hỗ trợ doanh nghiệp nhỏ và vừa. Chỉ viết phần "
                "gợi ý hành động dựa trên JSON đầu vào. Trạng thái eligibility là kết "
                "quả cố định: không thay đổi, phủ định hoặc suy diễn lại. Không thêm "
                "chính sách, điều kiện, mức tiền, thời hạn, thủ tục hay giấy tờ không "
                "có trong dữ liệu. Không nói doanh nghiệp chắc chắn sẽ nhận hỗ trợ. "
                "Không dùng tên field kỹ thuật, JSON, RAG, rule engine hoặc thuật ngữ "
                "nội bộ. Không lặp lại phần kết luận. Chỉ nêu 2-4 việc thực tế nên làm "
                "tiếp bằng tiếng Việt rõ ràng và ngắn gọn."
            ),
            "en": (
                "You are an SME support specialist. Only write action suggestions based on the input JSON. "
                "The eligibility status is a fixed result: do not change, negate, or re-infer it. "
                "Do not add policies, conditions, amounts, deadlines, procedures, or documents not in the data. "
                "Do not say the business will definitely receive support. "
                "Do not use technical field names, JSON, RAG, rule engine, or internal terms. "
                "Do not repeat the conclusion. "
                "Only list 2-4 practical next steps in clear, concise English."
            ),
        }
        lang = language if language in ADVISE_SYSTEM else "vi"
        payload: dict[str, Any] = {
            "model": config.ADVISORY_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": ADVISE_SYSTEM[lang],
                },
                {
                    "role": "user",
                    "content": json.dumps(advisory_payload, ensure_ascii=False, default=str),
                },
            ],
            "temperature": 0.2,
            "max_tokens": config.ADVISORY_MAX_TOKENS,
            "stream": False,
        }
        data = self._post(config.ADVISORY_CHAT_URL, config.ADVISORY_API_KEY, payload)
        message = (data.get("choices") or [{}])[0].get("message") or {}
        content = (message.get("content") or "").strip()
        if content:
            return content
        raise RuntimeError("LLM tư vấn trả content rỗng")

    # -- Translation of composed answers (answer provider) ------------------

    def translate_to_english(self, text: str) -> str | None:
        """Translate a composed Vietnamese answer; never adds or drops content."""
        if not config.answer_enabled() or not text.strip():
            return None
        payload: dict[str, Any] = {
            "model": config.ANSWER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Translate the user's text into clear English. Keep the meaning, "
                        "structure, line breaks, bullets and numbering exactly. Do not add, "
                        "remove, soften or strengthen any statement. Keep legal document "
                        "numbers (e.g. 80/2021/NĐ-CP) unchanged; render Điều/Khoản/Điểm as "
                        "Article/Clause/Point. Output only the translation."
                    ),
                },
                {"role": "user", "content": text},
            ],
            "temperature": 0,
            "max_tokens": config.ANSWER_MAX_TOKENS,
            "stream": False,
        }
        data = self._post(config.ANSWER_CHAT_URL, config.ANSWER_API_KEY, payload)
        message = (data.get("choices") or [{}])[0].get("message") or {}
        return (message.get("content") or "").strip() or None


# Backward-compatible alias so existing imports keep working.
FptClient = LLMClient


def _deterministic_rewrite(question: str, history: list[dict[str, str]]) -> str:
    """Fallback khong bia: ghep cau user gan nhat voi follow-up hien tai."""
    last_user = next(
        (m.get("content", "") for m in reversed(history) if m.get("role") == "user"),
        "",
    )
    if not last_user:
        return question
    return f"Ngu canh cau hoi truoc: {last_user}\nCau hoi tiep theo: {question}"


class PineconeDenseIndex:
    """Read-only adapter. Server A so huu viec tao index va upsert vectors."""

    def __init__(self) -> None:
        self._index: Any | None = None

    @property
    def enabled(self) -> bool:
        return config.pinecone_enabled()

    def _get_index(self):
        if self._index is not None:
            return self._index
        if not self.enabled:
            raise RuntimeError("Chua cau hinh Pinecone")
        try:
            from pinecone import Pinecone
        except ImportError as exc:
            raise RuntimeError("Thieu package pinecone") from exc
        client = Pinecone(api_key=config.PINECONE_API_KEY)
        if config.PINECONE_INDEX_HOST:
            self._index = client.Index(host=config.PINECONE_INDEX_HOST)
        else:
            self._index = client.Index(config.PINECONE_INDEX_NAME)
        return self._index

    def search(self, vector: list[float], top_k: int, filters: dict | None = None) -> list[tuple[str, float]]:
        kwargs: dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "include_values": False,
            "include_metadata": True,
            "namespace": config.PINECONE_NAMESPACE,
        }
        if filters:
            kwargs["filter"] = filters
        response = self._get_index().query(**kwargs)
        matches = getattr(response, "matches", None)
        if matches is None:
            matches = response.get("matches", []) if isinstance(response, dict) else []
        out = []
        for match in matches:
            if isinstance(match, dict):
                metadata = match.get("metadata") or {}
                physical_id = match.get("id")
                score = match.get("score", 0.0)
            else:
                metadata = getattr(match, "metadata", {}) or {}
                physical_id = getattr(match, "id", None)
                score = getattr(match, "score", 0.0)
            unit_id = (
                metadata.get("original_unit_id")
                or metadata.get("unit_id")
                or _decode_physical_unit_id(physical_id)
                or physical_id
            )
            if unit_id:
                out.append((str(unit_id), float(score)))
        return out


_ENCODED_UNIT_ID_RE = re.compile(r"^u_([0-9a-fA-F]+)$")


def _decode_physical_unit_id(value: Any) -> str | None:
    """Decode Server A's reversible ``u_<utf8 hex>`` Pinecone ID format."""
    if not isinstance(value, str):
        return None
    match = _ENCODED_UNIT_ID_RE.fullmatch(value)
    if not match or len(match.group(1)) % 2:
        return None
    try:
        return bytes.fromhex(match.group(1)).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
