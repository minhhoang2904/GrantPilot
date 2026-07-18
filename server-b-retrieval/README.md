# Server B — Hybrid legal retrieval

Luồng online:

`route -> exact Mongo lookup hoac query rewrite -> Pinecone -> hydrate MongoDB -> rerank -> parent context`

## Contract với Server A

Server A sở hữu:

- tạo/upsert Pinecone index;
- embedding documents bằng cùng `FPT_EMBEDDING_MODEL`;
- MongoDB collections `legal_documents`, `legal_units`, `policies`;
- `legal_units.unit_id` khớp `original_unit_id` trên Pinecone;
- `policies.evidence_unit_ids` tham chiếu legal units có thật.

Server B chỉ query. Pinecone record ID có thể chính là `unit_id` hoặc ID vật lý
dạng `u_<utf8 hex>`; khi encode, metadata phải có `original_unit_id` (ưu tiên)
hoặc `unit_id`. Namespace được cấu hình qua `PINECONE_NAMESPACE`. Text gốc và
metadata trích dẫn được hydrate từ MongoDB.

Text dùng để upsert nên giống `legal_store.embedding_text()`:

```text
{document_title}, số {document_number}
Điều {article}. {article_title}
Khoản {clause}, điểm {point}
{text}
```

## Cấu hình

Copy `.env.example` thành `.env`, nhưng không commit file có credential. Đặt
MongoDB Atlas connection string trong `MONGODB_URI`. Production nên cấu hình
`PINECONE_INDEX_HOST`; `PINECONE_INDEX_NAME` chỉ là fallback tiện cho dev.

Production dùng `LEGAL_DATA_BACKEND=mongodb`. Có thể đặt `jsonl` để chạy BM25
offline trong test/local; JSONL không còn là dependency production. `/health`
cho biết backend và các integration nào đã được cấu hình.

LLM được tách theo nhiệm vụ: `DeepSeek-V4-Flash` rewrite câu hỏi; `GLM-5.2`
viết final answer. Với grounded RAG, GLM thinking mặc định bị tắt và output
budget là 8192 để tránh trường hợp reasoning dùng hết completion budget nhưng
`content` rỗng. Có thể bật lại qua env sau khi benchmark.

## API

```bash
curl -X POST http://localhost:8001/retrieve \
  -H 'Content-Type: application/json' \
  -d '{"question":"Điều 17 khoản 2 điểm b quy định gì?","top_k":5}'
```

`POST /ask` nhận cùng payload, thêm `thread_id` để Redis giữ recent history cho
follow-up query rewrite.

## Test offline

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

Các test dùng fake Pinecone/FPT, không cần API key.
