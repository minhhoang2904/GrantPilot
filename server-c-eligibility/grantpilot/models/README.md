# src/models/ — Schema chung (contract)

Định nghĩa CHÍNH THỨC các cấu trúc dữ liệu (Pydantic). Mọi module import từ đây → không lệch schema.

| File | Định nghĩa | Tương ứng |
|---|---|---|
| `rule.py` | `Condition`, `RuleGroup`, `RuleResult` | cây điều kiện (dùng chung 2 tầng) |
| `qualification.py` | `Qualification` | **Tầng 1** — tư cách DNNVV KNST (`data/qualification.json`) |
| `program.py` | `Program`, `Benefit`, `RequiredDocument`, `Availability` | **Tầng 2** — 6 loại hỗ trợ (`data/programs.json`) |
| `profile.py` | `Profile` | hồ sơ DN |
| `eligibility_result.py` | `EligibilityResult`, `EligibilityStatus` | kết quả xét (5 trạng thái) |

Đặc tả từng trường: `docs/contracts.md`. Tên trường hồ sơ: `docs/field-dictionary.md`.

## Hai tầng
```
Qualification (tầng 1)  →  không đạt thì mọi Program tắt
      ▼
Program × 6 (tầng 2)    →  rule riêng + hồ sơ riêng + mức trần riêng
```
