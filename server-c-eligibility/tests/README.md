# tests/ — Kiểm thử

Hackathon không cần phủ rộng. CHỈ test phần logic dễ sai **âm thầm** (không crash, chỉ ra kết quả sai).

| Ưu tiên | Test gì | Vì sao |
|---|---|---|
| 🔴 Cao | `eligibility/logic.py` | Logic 4 giá trị + gộp all/any — sai ở đây là sai toàn hệ |
| 🔴 Cao | `eligibility/operators.py` | None → UNKNOWN (không phải FAIL) |
| 🔴 Cao | `eligibility/engine.py` | 2 tầng, kế thừa status khi tầng 1 trượt |
| 🟡 Vừa | `benefit.py` | Áp đúng mức trần, computable=False khi thiếu số |
| 🟡 Vừa | `ranking.py` | Không cộng trùng program xung khắc |
| ⚪ Thấp | retrieval, LLM | Kiểm bằng 6 test case ở `benchmark/` |

## Ca test tối thiểu — logic.py
- `all`: có 1 FAIL + 1 UNKNOWN → **FAIL** (FAIL thắng) ← Case 3
- `all`: có UNKNOWN + NEEDS_REVIEW, không FAIL → **UNKNOWN** (hỏi user trước)
- `all`: tất cả PASS → **PASS**
- `any`: có 1 PASS + 1 FAIL → **PASS**
- `any`: có UNKNOWN + FAIL, không PASS → **UNKNOWN**
- Group lồng nhau 2 tầng → gộp đúng

## Ca test tối thiểu — operators.py
- `None` với mọi toán tử → **UNKNOWN**, không ném exception
- `in` / `not_in` với list
- `0` và `false` là giá trị THẬT (không nhầm với None)

## Ca test tối thiểu — engine.py
- Tầng 1 trượt → mọi program kế thừa status, không xét tầng 2
- `availability.status = "unknown"` → **PROGRAM_UNAVAILABLE** ← Case 5
- Thiếu required_document → **NEED_MORE_INFO** + missing_documents ← Case 4
- Rule `review_status: "draft"` → bị bỏ qua + ghi log
- Leaf `evaluation: "human_review"` → **NEEDS_REVIEW** lan lên đúng
