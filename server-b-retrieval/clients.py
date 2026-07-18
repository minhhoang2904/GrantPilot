"""External clients cho FPT va Pinecone, co the inject fake trong test."""

from __future__ import annotations

import re
from typing import Any

import config


class FptClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else config.FPT_API_KEY).strip()

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Chua cau hinh FPT_API_KEY")
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError("Thieu package httpx") from exc
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "GrandPilot-Retrieval/1.0",
        }
        with httpx.Client(timeout=config.FPT_TIMEOUT_SECONDS) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def _post_chat(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Gui chat payload, retry neu FPT proxy chua pass-through GLM controls."""
        try:
            return self._post(config.FPT_CHAT_URL, payload)
        except Exception as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            has_glm_controls = "thinking" in payload or "reasoning_effort" in payload
            if not has_glm_controls or status_code not in {400, 422}:
                raise
            compatible = dict(payload)
            compatible.pop("thinking", None)
            compatible.pop("reasoning_effort", None)
            return self._post(config.FPT_CHAT_URL, compatible)

    def embed(self, texts: list[str]) -> list[list[float]]:
        data = self._post(
            config.FPT_EMBEDDINGS_URL,
            {
                "model": config.FPT_EMBEDDING_MODEL,
                "input": texts,
                "encoding_format": "float",
            },
        )
        rows = sorted(data.get("data", []), key=lambda item: item.get("index", 0))
        if len(rows) != len(texts):
            raise RuntimeError(f"Embedding API tra {len(rows)}/{len(texts)} vectors")
        return [row["embedding"] for row in rows]

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        data = self._post(
            config.FPT_RERANK_URL,
            {
                "model": config.FPT_RERANK_MODEL,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
            },
        )
        return [
            (int(item["index"]), float(item.get("relevance_score", item.get("score", 0.0))))
            for item in data.get("results", [])
        ]

    def rewrite_query(self, question: str, history: list[dict[str, str]]) -> str:
        if not self.enabled or not config.FPT_QUERY_REWRITE_MODEL or not history:
            return _deterministic_rewrite(question, history)
        prior = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
        data = self._post_chat(
            {
                "model": config.FPT_QUERY_REWRITE_MODEL,
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
                "max_tokens": config.FPT_QUERY_REWRITE_MAX_TOKENS,
                "stream": False,
            },
        )
        content = data["choices"][0]["message"].get("content") or ""
        return content.strip() or _deterministic_rewrite(question, history)

    def answer(self, question: str, evidence: list[dict]) -> str | None:
        if not self.enabled or not config.FPT_ANSWER_MODEL or not evidence:
            return None
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
            "model": config.FPT_ANSWER_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Bạn là trợ lý tra cứu pháp luật. Chỉ trả lời bằng bằng chứng "
                        "được cung cấp. Mỗi khẳng định pháp lý phải dẫn số văn bản và "
                        "Điều/Khoản/Điểm. Nếu bằng chứng không đủ, nói rõ là không đủ. "
                        "Không tự kết luận doanh nghiệp chắc chắn đủ điều kiện."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Bằng chứng:\n\n{evidence_text}\n\nCâu hỏi: {question}",
                },
            ],
            "temperature": 0,
            "max_tokens": config.FPT_ANSWER_MAX_TOKENS,
            "stream": False,
        }
        if config.FPT_ANSWER_MODEL.lower().startswith("glm-5.2"):
            payload["thinking"] = {
                "type": config.FPT_ANSWER_THINKING,
                "clear_thinking": True,
            }
            payload["reasoning_effort"] = config.FPT_ANSWER_REASONING_EFFORT

        data = self._post_chat(payload)
        choice = data.get("choices", [{}])[0]
        message = choice.get("message") or {}
        content = (message.get("content") or "").strip()
        if content:
            return content
        finish_reason = choice.get("finish_reason", "unknown")
        reasoning_present = bool((message.get("reasoning_content") or "").strip())
        raise RuntimeError(
            "LLM trả content rỗng "
            f"(model={config.FPT_ANSWER_MODEL}, finish_reason={finish_reason}, "
            f"reasoning_content={reasoning_present}, max_tokens={config.FPT_ANSWER_MAX_TOKENS})"
        )


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
            # Server A co the encode ID vat ly thanh ``u_<hex>`` de Pinecone
            # chi nhan ASCII. Retrieval phai hop nhat theo ID phap ly goc,
            # khong theo ID luu tru. Ho tro ca contract cu ``unit_id``.
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
