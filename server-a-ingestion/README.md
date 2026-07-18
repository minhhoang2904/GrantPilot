# Legal data pipeline

Luồng dữ liệu:

`PDF scan -> OCR/parse -> MongoDB -> embedding -> Pinecone legal_units`

- Retrieval tìm trên `legal_units`; đây là nguyên văn có Điều/Khoản/Điểm và số trang.
- `policies.json` là output review/audit. MongoDB `policies` là nguồn dữ liệu của policy/rule cho các service.
- `evidence_unit_ids` nối mỗi policy trở lại đúng phần nguyên văn.

## 1. Chuẩn bị

```bash
brew install poppler tesseract tesseract-lang
cd server-a-ingestion
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Thu hồi API key đã gửi trong hội thoại, tạo key mới, rồi đặt trong terminal (không ghi key vào file code):

```bash
export FPT_API_KEY="YOUR_NEW_KEY"
```

Hoặc copy `.env.example` thành `.env` và điền key mới. `.env` đã được gitignore.

Kiểm tra và điền đúng metadata/URL trong `source_documents.json` trước khi ingest.

## 2. Chạy pipeline

```bash
python pipeline.py all
```

Trong lúc phát triển có thể chạy một PDF trước:

```bash
python pipeline.py all --pdf 04.signed.pdf
```

Pipeline cache OCR, kết quả bóc policy theo Điều, và embedding không đổi. Có thể chạy lại an toàn. Muốn ép tạo lại:

```bash
python pipeline.py all --force-ocr --force-policy --force-embed
```

Output:

- `data/processed/ocr/<pdf>/pages.jsonl`: text OCR theo trang.
- `shared/legal/legal_units.jsonl`: records Điều/Khoản/Điểm cho RAG.
- `shared/legal/policies.json`: canonical policy records.
- `shared/legal/policy_candidates.json`: policy records do LLM sinh, cần review.
- Pinecone namespace `legal_units`: vector database cho các `legal_units`.

## 3. MongoDB và API nội bộ

Luồng ingest là `PDF -> OCR/parse -> MongoDB -> embedding -> Pinecone`. MongoDB lưu hai collection:

- `legal_documents`: `document_id`, `version`, `is_current`, `document_number`, `document_title`, `issued_date`, `effective_from`, `effective_to`, `status`, `source_url`, `checksum`, `ingested_at`.
- `legal_units`: `unit_id`, `document_id`, `version`, `is_current`, Điều/Khoản/Điểm/Chương/Mục, `page_start`, `page_end`, `text`, `normalized_text`, `source_url` và metadata hiệu lực.

Chạy API:

```bash
uvicorn api:app --host 0.0.0.0 --port 8000
```

Hai endpoint cho Server B:

```bash
curl -X POST http://localhost:8000/internal/legal-units/batch \
  -H 'content-type: application/json' \
  -d '{"unit_ids":["law-04-2017-qh14_art-8_cl-3"]}'

curl 'http://localhost:8000/internal/legal-units/exact?document_number=04%2F2017%2FQH14&article=12&clause=3&point=b'
```

Nạp dữ liệu hiện có vào MongoDB (không lưu binary PDF):

```bash
python ingest_mongodb.py
```

Script tính SHA-256 cho mỗi PDF để tránh trùng, lưu metadata/version vào `legal_documents`,
đẩy units vào `legal_units`, rồi upsert toàn bộ `policies.json` vào collection `policies`.
Nó nhận cả tên biến `MONGO_URI`/`MONGO_DB` và `MONGODB_URI`/`MONGODB_DB`.

## 4. Rule normalization và review gate

`fact-catalog-v1.json` là hợp đồng field dùng chung. Có thể trỏ tới catalog Huy chốt bằng:

```bash
export FACT_CATALOG_PATH=/absolute/path/to/fact-catalog-v1.json
```

Ingest chỉ giữ rule có `field` trong catalog và kiểm tra kiểu dữ liệu, enum, operator và nguồn fact (`direct`/`derived`).
`contains` không bị đổi thành `in`: `contains` kiểm tra substring/phần tử của danh sách, còn `in` kiểm tra giá trị thực tế thuộc danh sách cho phép.

Trạng thái chuẩn: `candidate`, `needs_schema_mapping`, `approved`, `rejected`, `superseded`.
Chỉ record có đủ `review_status=approved`, `is_current=true`, evidence chính xác cấp khoản/điểm và không có warning mới được đánh dấu `eligible_for_decision=true`.
Evidence chỉ resolve tới Điều luôn mang `evidence_resolution=article_fallback`, `requires_evidence_review=true` và không được đưa vào decision.

Hai entrypoint `python pipeline.py all` và `python ingest_mongodb.py` đều gọi chung `persist_policies()` để ghi policy qua cùng validation gate.

## 5. Test retrieval

```bash
python retrieve.py "Startup công nghệ được hỗ trợ những gì?" --top-k 5
```

Query và documents bắt buộc dùng cùng model `Vietnamese_Embedding`.

## 6. Test offline

```bash
python -m unittest -v test_pipeline.py
```
