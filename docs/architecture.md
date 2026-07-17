# Kiến trúc GrantPilot

## Nguyên tắc thiết kế

1. **Nghiệp vụ hẹp, engine tổng quát.** MVP chỉ phục vụ startup phần mềm, nhưng rule engine
   (nested all/any + 8 toán tử) đủ tổng quát để thêm FDI/công nghệ cao sau — không viết lại engine,
   chỉ thêm field + rule.
2. **Tách "tìm" và "xét".** RAG tìm hỗ trợ liên quan (mờ). Eligibility Engine xét điều kiện (chính xác).
3. **LLM để *hiểu*, code để *quyết định*.** LLM bóc rule (có người review) + diễn giải kết quả.
   Quyết định đúng/sai là của code.
4. **Thà không kết luận còn hơn kết luận sai.** 5 trạng thái thay vì bool.

## Mô hình HAI TẦNG

```
TẦNG 1 — TƯ CÁCH  (data/qualification.json — 1 bộ rule)
   "DN có phải DNNVV khởi nghiệp sáng tạo không?"
   = là SME + ≤5 năm + chưa chào bán CK + có tính đổi mới
   → KHÔNG ĐẠT thì mọi program tầng 2 tắt, kế thừa status
        │
        ▼
TẦNG 2 — TỪNG HỖ TRỢ  (data/programs.json — 6 program)
   mỗi program: rules riêng + required_documents + benefit (trần/chu kỳ)
                + conflicts_with + availability
```

Nhờ tách tầng, diễn đạt được: *"Bạn **thuộc diện** DNNVV KNST ✅, nhưng để nhận hỗ trợ
thuê coworking thì **còn thiếu hợp đồng thuê**"* (Case 4).

## Luồng A — Chuẩn bị (offline, 1 lần)

```
data/raw/ (Luật 04/2017/QH14, NĐ 80/2021/NĐ-CP)
   │  ingestion/parser.py        → tách Chương/Điều/Khoản
   │  ingestion/chunker.py       → chunk theo cấu trúc + metadata + ngữ cảnh cha
   │  ingestion/rule_extractor.py→ bóc điều kiện → rule (LLM gợi ý + NGƯỜI review chéo)
   ▼
   ├─► ingestion/embedder.py     → VECTOR STORE              (để TÌM)
   └─► data/qualification.json + data/programs.json          (để XÉT)
```

> ⚠️ `rule_extractor` chỉ **gợi ý**. Rule chỉ được bật khi `review_status = manually_reviewed`
> (Thành bóc → Hoàng đọc nguyên văn kiểm → đồng ý). Xem quy trình ở `data/README.md`.

## Luồng B — Trả lời user (online)

```
Câu hỏi + hồ sơ DN
   │  (1) chatbot/profile_builder.py  → profile (chưa khai = None, KHÔNG phải false)
   │  (2) retrieval/retriever.py      → hybrid search → program liên quan
   │  (3) eligibility/engine.py
   │        ├─ check_qualification()  → TẦNG 1
   │        └─ check_program()        → TẦNG 2, dùng logic.py (4 giá trị)
   │             ├─ kiểm required_documents
   │             └─ benefit.estimate() → computable=False nếu chưa rõ trần
   │  (4) eligibility/gap_analysis.py → thiếu gì, cứng/mềm, hỏi field nào
   │  (5) eligibility/ranking.py      → xếp hạng, xung khắc, tổng tiềm năng (không cộng trùng)
   │  (6) chatbot/answer_generator.py → LLM diễn giải + trích dẫn
   ▼
   ui/app.py
```

## Logic 4 giá trị — trái tim engine

Mỗi điều kiện trả `PASS | FAIL | UNKNOWN | NEEDS_REVIEW`, gộp lên group theo:

```
all (AND):  FAIL  >  UNKNOWN  >  NEEDS_REVIEW  >  PASS
any (OR) :  PASS  >  UNKNOWN  >  NEEDS_REVIEW  >  FAIL
```

Ánh xạ ra status: PASS→LIKELY_ELIGIBLE · FAIL→NOT_ELIGIBLE · UNKNOWN→NEED_MORE_INFO ·
NEEDS_REVIEW→NEEDS_HUMAN_REVIEW. (`PROGRAM_UNAVAILABLE` đến từ `program.availability`.)

Chi tiết & lý do chọn thứ tự: `docs/contracts.md` mục C.

## Vì sao có Vector Store VÀ file JSON?

- **Vector Store**: chunk nhỏ + embedding → tối ưu **search ngữ nghĩa**.
- **qualification/programs.json**: bản ghi đầy đủ + rule có cấu trúc → tối ưu **xét logic & trích dẫn**.
- Nối bằng **`program_id`**: chunk tìm được → lấy program_id → tra ra bản đầy đủ.

> Có thể để chung 1 database. Điều quan trọng: **rule ở cấp *program*, chunk ở cấp *khoản*** —
> đừng chép rule xuống từng chunk.

## Bản đồ module

| Phần | Module | Chủ |
|---|---|---|
| Dữ liệu 2 tầng | `data/` | Thành |
| Ingestion / bóc rule | `src/ingestion/` | Thành |
| Hồ sơ DN | `src/chatbot/profile_builder.py` | Huy |
| Retrieval | `src/retrieval/` | Huy |
| Logic 4 giá trị | `src/eligibility/logic.py` | Hoàng |
| Engine 2 tầng | `src/eligibility/engine.py` | Hoàng |
| Benefit / Gap / Rank | `src/eligibility/` | Hoàng |
| Sinh câu trả lời | `src/chatbot/answer_generator.py` | Huy |
| UI | `ui/` | Hoàng |
| 6 test case + metric | `benchmark/` | Hoàng |
