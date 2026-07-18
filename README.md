# GrantPilot

Hệ thống tư vấn chính sách hỗ trợ doanh nghiệp: tra cứu chính sách, kiểm tra điều kiện hưởng (eligibility) và trả lời câu hỏi dựa trên hồ sơ doanh nghiệp.

## Cấu trúc thư mục

```
policy-advisor/
├── server-a-ingestion/   # Thành — nạp & chuẩn hoá dữ liệu chính sách vào DB dùng chung
├── server-b-retrieval/   # Huy — API tra cứu chính sách + sinh câu trả lời
├── server-c-eligibility/ # Hoàng — API kiểm tra điều kiện hưởng & xếp hạng chính sách
├── frontend/             # React + Vite + Tailwind CSS (thay thế Streamlit)
└── shared/               # DB SQLite dùng chung + schema
```

Mỗi thư mục là **1 service độc lập**, mỗi người chỉ commit vào folder của mình để giảm conflict tối đa.

## Yêu cầu

- Python 3.10+
- Node.js 20+ (cho frontend React)
- (Tuỳ chọn) Docker + Docker Compose

## Setup nhanh (local, không Docker)

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
# 4. Chạy frontend React (port 5173)
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173 trong trình duyệt.

### Frontend — React SPA

Frontend là Vite + TypeScript + Tailwind CSS. Cấu trúc `src/`:

- `auth.ts` — lưu email đăng nhập vào `localStorage` (mock mode; thay bằng Google Identity để dùng OAuth thật).
- `api.ts` — toàn bộ `fetch` call tới Server B qua Vite proxy `/api/*` → `localhost:8001`.
- `types.ts` — kiểu dữ liệu dùng chung (`Company`, `PolicyResult`, `Message`...).
- `pages/LoginPage.tsx` — màn hình đăng nhập.
- `pages/OnboardingPage.tsx` — form hồ sơ doanh nghiệp 1 lần cho email mới.
- `pages/MainPage.tsx` — layout chính: sidebar + tab Chat + tab Benchmark.
- `components/ChatThread.tsx` + `ChatInput.tsx` — chat bubbles + input.
- `components/ResultsTable.tsx` + `GapDetail.tsx` — bảng kết quả eligibility.
- `components/BenchmarkPanel.tsx` — so sánh Eligibility Engine vs. RAG phẳng.

Trong dev, Vite proxy tự chuyển `/api/*` → `http://localhost:8001/*` (xem `vite.config.ts`), không cần cấu hình CORS trên Server B.

Biến môi trường: sao chép `.env.example` thành `.env.local` và điền giá trị nếu cần.

## Setup bằng Docker Compose

```bash
docker compose up --build
```

Lệnh này sẽ chạy `server-a-ingestion` (nạp dữ liệu 1 lần), rồi khởi động `server-b-retrieval`, `server-c-eligibility` và `frontend`. Xem chi tiết trong `docker-compose.yml`.

## Quy ước

- **Không commit** `.env.local`, `*.db`, `chroma_db/`, `node_modules/`. Xem `.gitignore`.
- `shared/schema.sql` là nguồn duy nhất cho cấu trúc DB — mọi thay đổi schema phải qua PR review chung.
- Mỗi service expose API riêng, giao tiếp qua HTTP.
