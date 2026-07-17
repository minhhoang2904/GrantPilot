# Legal data pipeline

Luồng dữ liệu:

`PDF scan -> OCR -> legal_units.jsonl -> policies.json + Chroma legal_units`

- Retrieval tìm trên `legal_units`; đây là nguyên văn có Điều/Khoản/Điểm và số trang.
- `policies.json` là dữ liệu nghiệp vụ có cấu trúc để bước eligibility sử dụng sau.
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
- `data/processed/legal_units.jsonl`: records Điều/Khoản/Điểm cho RAG.
- `data/policies.json`: policies có `evidence_unit_ids`.
- `data/chroma`: vector database collection `legal_units`.

## 3. Test retrieval

```bash
python retrieve.py "Startup công nghệ được hỗ trợ những gì?" --top-k 5
```

Query và documents bắt buộc dùng cùng model `Vietnamese_Embedding`.

## 4. Test offline

```bash
python -m unittest -v test_pipeline.py
```
