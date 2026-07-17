# src/eligibility/ — Bộ máy xét điều kiện (chủ: Hoàng) ⭐ ĐIỂM KHÁC BIỆT

Đối chiếu hồ sơ DN với điều kiện → ra 1 trong **5 trạng thái**. Thuần LOGIC CODE, không LLM.

## Định vị sản phẩm (nhớ khi code)
> Đây là **công cụ sàng lọc sơ bộ cơ hội hỗ trợ và hướng dẫn chuẩn bị hồ sơ**,
> KHÔNG phải "hệ thống kết luận pháp lý chắc chắn được nhận hỗ trợ".
> Đủ điều kiện pháp lý ≠ chắc chắn được cấp tiền.

## Các file

| File | Nhiệm vụ |
|---|---|
| `operators.py` | 8 toán tử so sánh (`==` `!=` `<` `<=` `>` `>=` `in` `not_in`). None → UNKNOWN. |
| `logic.py` | ⭐ Logic 4 giá trị (PASS/FAIL/UNKNOWN/NEEDS_REVIEW) + quy tắc gộp `all`/`any` đệ quy. |
| `engine.py` | ⭐ Xét 2 tầng: `check_qualification` (tư cách) → `check_program` (từng hỗ trợ). |
| `benefit.py` | Tính mức hỗ trợ: tỉ lệ × chi phí, áp mức trần, chu kỳ. Thiếu số → `computable=False`. |
| `gap_analysis.py` | Thiếu gì, cứng hay mềm, hỏi field nào, cần hồ sơ nào, gợi ý khắc phục. |
| `ranking.py` | Xếp hạng, cảnh báo xung khắc, tổng giá trị tiềm năng (chống cộng trùng). |

## Luồng
```
profile + qualification + list[Program]
  → engine.check_qualification()          → TẦNG 1: tư cách
      └─ không đạt → mọi program kế thừa status, dừng
  → engine.check_program() cho từng program → TẦNG 2
      ├─ logic.evaluate_node() (đệ quy, 4 giá trị)
      ├─ kiểm required_documents
      └─ benefit.estimate()
  → gap_analysis.analyze()                → thiếu gì, khắc phục ra sao
  → ranking.rank_and_summarize()          → xếp hạng + cảnh báo + tổng tiềm năng
```

## 5 trạng thái
| Status | Nghĩa |
|---|---|
| `LIKELY_ELIGIBLE` | Có khả năng đủ điều kiện |
| `NOT_ELIGIBLE` | Có điều kiện rõ ràng không đạt |
| `NEED_MORE_INFO` | Thiếu dữ liệu hoặc thiếu hồ sơ chứng minh |
| `NEEDS_HUMAN_REVIEW` | Cần chuyên gia/cơ quan xác minh |
| `PROGRAM_UNAVAILABLE` | Có căn cứ nhưng chưa rõ chương trình đang mở |

## Nguyên tắc bất di bất dịch
1. **Không LLM** trong quyết định đúng/sai.
2. **None ≠ False.** Chưa khai → UNKNOWN → NEED_MORE_INFO. Không bao giờ tự suy thành trượt.
3. **Không bịa số.** Thiếu rate/cap → `computable=False`.
4. **Không cộng trùng.** Loại xung khắc trước khi cộng tổng.
5. **Mỗi kết luận kèm trích dẫn** điều/khoản.
6. Chỉ dùng rule `review_status >= manually_reviewed`.
