# Policy Advisor

Hệ thống tư vấn chính sách hỗ trợ doanh nghiệp: tra cứu chính sách, kiểm tra điều kiện hưởng (eligibility) và trả lời câu hỏi dựa trên hồ sơ doanh nghiệp.

## Cấu trúc thư mục

```
policy-advisor/
├── server-a-ingestion/   # Thành — nạp & chuẩn hoá dữ liệu chính sách vào DB dùng chung
├── server-b-retrieval/   # Huy — API tra cứu chính sách + sinh câu trả lời
├── server-c-eligibility/ # Hoàng — API kiểm tra điều kiện hưởng & xếp hạng chính sách
├── frontend/             # Streamlit UI
└── shared/                # DB SQLite dùng chung + schema
```

Mỗi thư mục là **1 service độc lập**, mỗi người chỉ commit vào folder của mình để giảm conflict tối đa.

## Yêu cầu

- Python 3.10+
- (Tuỳ chọn) Docker + Docker Compose

## Setup nhanh (local, không Docker)

Mỗi service có `requirements.txt` riêng, nên cài trong virtualenv riêng (hoặc dùng chung 1 venv nếu team đồng thuận):

```bash
# 1. Nạp dữ liệu chính sách vào shared/policy.db
cd server-a-ingestion
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python ingest.py
deactivate

# 2. Chạy server retrieval (port 8001)
cd ../server-b-retrieval
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8001
```

Mở terminal khác cho từng service:

```bash
# 3. Chạy server eligibility (port 8002)
cd server-c-eligibility
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8002
```

```bash
# 4. Chạy frontend Streamlit (port 8501)
cd frontend
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # rồi điền giá trị thật
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Setup bằng Docker Compose

```bash
docker compose up --build
```

Lệnh này sẽ chạy `server-a-ingestion` (nạp dữ liệu 1 lần), rồi khởi động `server-b-retrieval`, `server-c-eligibility` và `frontend`. Xem chi tiết trong `docker-compose.yml`.

## Quy ước

- **Không commit** `secrets.toml`, `*.env`, `*.db`, `chroma_db/`. Xem `.gitignore`.
- `shared/schema.sql` là nguồn duy nhất cho cấu trúc DB — mọi thay đổi schema phải qua PR review chung.
- Mỗi service expose API riêng, giao tiếp qua HTTP (xem `frontend/app.py` để biết cách gọi).
