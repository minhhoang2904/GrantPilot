# Form hỏi gì & lưu trữ gì — hồ sơ doanh nghiệp

> Suy ra từ **rulebook thật** (`shared/rulebook/`) và code engine (`server-c-eligibility/grantpilot/`),
> không phải từ `field-dictionary.md` — từ điển liệt kê cả trường chưa dùng.
>
> Liên quan: `docs/contracts.md` mục F · `docs/field-dictionary.md` · `docs/SPEC-server-a-va-server-b.md`

---

# PHẦN 1 — FORM HỎI GÌ

## 10 trường là đủ trả lời trọn vẹn (cho program `coworking_rent_support`)

Xếp theo **thứ tự hỏi**, không theo nhóm logic. Lý do ở mục "Vì sao thứ tự này".

### Vòng 1 — Chặn sớm (2 câu)
| Hỏi | Trường | Vì sao hỏi đầu |
|---|---|---|
| "DN thành lập năm nào?" | `founded_year` | Điều kiện **cứng** ≤5 năm. Trượt là kết luận ngay. |
| "DN đã chào bán chứng khoán ra công chúng chưa?" | `is_public_offering` | Điều kiện **cứng**. |

→ Trượt một trong hai: trả `NOT_ELIGIBLE` + trích dẫn, **dừng, không hỏi thêm 8 câu nữa**.

### Vòng 2 — Phân hạng DNNVV (3 câu)
| Hỏi | Trường | Ghi chú |
|---|---|---|
| "DN hoạt động lĩnh vực gì?" | `sector` | enum, không free-text |
| "Bao nhiêu lao động **tham gia BHXH**?" | `social_insurance_employees` | ⚠️ phải nói rõ "BHXH", không phải tổng nhân sự |
| "Doanh thu năm gần nhất?" **hoặc** "Tổng nguồn vốn?" | `annual_revenue_vnd` \| `total_capital_vnd` | Luật dùng **HOẶC** — hỏi một cái, cho phép đổi sang cái kia. Đừng bắt khai cả hai. |

→ Ba câu này chỉ sinh **một** giá trị: `sme_size_category`. Đắt nhưng không bỏ được — nó vừa là
điều kiện tầng 1 (`is_dnnvv`), vừa là khoá tra `benefit.tiers` để biết mức hỗ trợ hạng nào.

### Vòng 3 — Tính đổi mới (2 câu)
| Hỏi | Trường | Ghi chú |
|---|---|---|
| "Sản phẩm chính của DN?" | `product_type` | enum: software/mobile_app/cloud/ai/platform/… |
| "DN có bằng sáng chế / GPHI không?" | `has_patent` | Nhánh dự phòng — hai nhánh nối bằng `any` |

→ Cả hai trượt/thiếu → rơi xuống `is_innovative` (`human_review`) → `NEEDS_HUMAN_REVIEW`.
**Không hỏi user `is_innovative`** — đó là đánh giá của cơ quan, không phải của DN tự khai.

### Vòng 4 — Địa bàn (1 câu)
| Hỏi | Trường | Vì sao |
|---|---|---|
| "DN ở tỉnh/thành nào?" | `province` | NĐ 80 triển khai qua UBND tỉnh — chương trình, ngân sách, hạn nộp là chuyện của tỉnh |

⚠️ Nói rõ lý do khi hỏi: *"để biết chương trình ở tỉnh bạn có đang mở nhận hồ sơ không"*.
Hỏi khơi khơi thì user không hiểu vì sao cần.

### Vòng 5 — Chỉ khi ĐÃ `LIKELY_ELIGIBLE` (2 câu/program)
| Hỏi | Trường | Ghi chú |
|---|---|---|
| "Đã có hợp đồng thuê tại cơ sở ươm tạo/coworking chưa?" | `has_coworking_contract` | điều kiện tầng 2 + checklist hồ sơ |
| "Chi phí thuê hằng tháng bao nhiêu?" | `coworking_monthly_cost_vnd` | **để tính ra tiền** |

→ Hỏi **cuối cùng và chỉ khi đủ điều kiện**. Bắt người ta khai chi phí cho một hỗ trợ họ
không đủ điều kiện nhận là làm phiền vô ích.

## Vì sao thứ tự này

Trong nhóm `all`, engine ưu tiên **`FAIL` > `UNKNOWN`** (xem `grantpilot/logic.py`). Nghĩa là
một điều kiện cứng trượt → kết luận ngay, không cần biết gì thêm.

Khai thác đúng cái đó: DN 7 tuổi → `NOT_ELIGIBLE` sau **đúng một câu hỏi**, kèm trích dẫn.
Hỏi ngược lại thì user khai xong 9 trường mới bị báo trượt vì cái tuổi lẽ ra biết ngay từ câu
đầu — thiết kế thù địch với người dùng.

## Form KHÔNG được cứng

Rulebook mới có **1/6 program** điền thật. Khi Thành điền tiếp, mỗi program kéo theo trường chi
phí riêng (`product_testing_cost_vnd`, `ip_consulting_cost_vnd`…) + hồ sơ riêng.

Cách đúng: hỏi 8 trường chung → xét tầng 1 → **chỉ hỏi chi phí/giấy tờ của program đã
`LIKELY_ELIGIBLE`**. Đây chính là lý do `eligibility_result` trả `missing_fields`:
dùng nó để hỏi vòng sau, thay vì đoán trước một form 20 ô.

## TUYỆT ĐỐI không hỏi

| Trường | Vì sao |
|---|---|
| `sme_size_category` | Trường **dẫn xuất** — `classifier.py` tính. DN mà tự biết mình hạng nhỏ hay vừa thì đã chẳng cần sản phẩm này. |
| `company_age_years` | Dẫn xuất từ `founded_year`. Hỏi năm thành lập, đừng hỏi số tuổi. |
| `is_innovative` | Đánh giá của cơ quan (`evaluation: human_review`), không phải DN tự khai. |
| `employee_count` (tổng nhân sự) | **Không rule nào đọc.** Hỏi cả nó lẫn số BHXH sẽ khiến user lẫn hai con số → phân hạng sai. |
| `has_tax_debt`, `has_administrative_violation`, `received_support_program_ids` | Đang gắn ⏳ trong từ điển — **chưa rule nào dùng**. Hỏi mà không dùng vừa làm phiền vừa tạo ảo giác sản phẩm chặt chẽ hơn thực tế. Chờ có nguồn. |

---

# PHẦN 2 — LƯU TRỮ GÌ

## ⚠️ Bảng `profiles` hiện tại không chở nổi hồ sơ engine cần

`shared/schema.sql` đang là:

```sql
profiles(id, business_name, industry, business_type, num_employees,
         province, annual_revenue, founded_year, extra_attributes, ...)
```

| Cột hiện tại | Vấn đề |
|---|---|
| `num_employees` | DNNVV xét theo **lao động BHXH**, không phải tổng nhân sự. Hai số này khác nhau thật. Dùng nhầm → phân hạng sai, **mà sai im lặng**. |
| `annual_revenue REAL` | Tiền phải là **số nguyên VNĐ**. `REAL` gây sai số làm tròn ngay tại ngưỡng — đúng chỗ không được sai. |
| `industry` | Rule đọc `sector` (enum). Cần đổi tên hoặc map. |
| `business_type` | **Không rule nào đọc.** |
| *(thiếu)* | `total_capital_vnd`, `is_public_offering`, `product_type`, `has_patent`, các trường chi phí |

## Đề xuất `profiles`

```sql
CREATE TABLE IF NOT EXISTS profiles (
    id                          TEXT PRIMARY KEY,
    company_name                TEXT,      -- chỉ hiển thị, không rule nào đọc

    -- tầng 0: phân hạng DNNVV
    sector                      TEXT,      -- enum, xem field-dictionary
    social_insurance_employees  INTEGER,   -- ⚠️ BHXH, KHÔNG phải tổng nhân sự
    annual_revenue_vnd          INTEGER,   -- ⚠️ INTEGER, không REAL
    total_capital_vnd           INTEGER,   -- doanh thu HOẶC nguồn vốn, chỉ cần một

    -- tầng 1: tư cách
    founded_year                INTEGER,   -- ⚠️ lưu NĂM, không lưu số tuổi
    is_public_offering          INTEGER,   -- 0/1/NULL
    product_type                TEXT,
    has_patent                  INTEGER,   -- 0/1/NULL

    -- địa bàn: tra availability
    province                    TEXT,

    -- tầng 2: hồ sơ chứng từ
    has_coworking_contract      INTEGER,   -- 0/1/NULL
    has_business_registration   INTEGER,   -- 0/1/NULL

    -- chi phí thực tế: để tính tiền (thêm dần theo program Thành điền)
    coworking_monthly_cost_vnd  INTEGER,

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

## Ba quy tắc lưu trữ — sai một cái là hỏng cả hệ

### 1. ⚠️ `NULL` phải sống sót qua DB

Đây là quy tắc quan trọng nhất. Engine phân biệt **`None` (chưa khai)** với **`False`/`0`
(khai là không)**:
- `None` → `UNKNOWN` → `NEED_MORE_INFO` → hỏi lại user
- `False` → so sánh thật → có thể `PASS` hoặc `FAIL`

Trong SQLite, boolean lưu bằng `INTEGER`: `NULL` / `0` / `1`. Nếu code đọc DB mà coerce
`NULL → 0` (hay dùng `bool(row["has_patent"])`, hay `.get(k, False)`), thì **"chưa khai" biến
thành "khai là không"** → engine trả `NOT_ELIGIBLE` cho DN đủ điều kiện thật, **và không ai biết**.

Toàn bộ cơ chế chống hallucination sụp đổ đúng tại dòng đọc DB đó. Không dùng default `False`,
không dùng `or`, không `bool()`. Đọc thẳng, giữ `None`.

### 2. Lưu SỰ THẬT, tính DẪN XUẤT lúc đọc

**Không lưu** `sme_size_category` và `company_age_years` vào DB.

- `company_age_years` **thay đổi theo thời gian** — DN lưu "4 tuổi" hôm nay, sang năm thành 5.
  Lưu số tuổi là ướp một giá trị sẽ tự sai. Lưu `founded_year`, tính tuổi tại `evaluated_at`.
- `sme_size_category` phụ thuộc **bảng ngưỡng**. Thành sửa ngưỡng trong
  `sme_classification.json` → mọi hạng đã lưu thành sai, âm thầm. Để `classifier.py` tra lại
  mỗi lần xét.

Nguyên tắc: **DB lưu cái DN khai; engine tính cái suy ra được.**

### 3. Không lưu cái không dùng

Mỗi cột phải trả lời được: *rule nào đọc nó?* Không có rule nào → không có cột.
`business_type` và `employee_count` rơi vào diện này.

Đây vừa là chuyện gọn, vừa là chuyện dữ liệu doanh nghiệp: thu và giữ thứ mình không dùng
thì không biện minh được nếu bị hỏi.

Trường ⏳ (`has_tax_debt`…): để trong `field-dictionary.md` là đủ — **chưa thêm cột, chưa hỏi**,
tới khi có `source_document` + `article` thật.

---

# Việc cần quyết

1. **Sửa `profiles` trong `schema.sql`?** README nói mọi thay đổi schema phải qua PR review chung
   → nhánh `feat/eligibility-engine-2tang` **chưa đụng vào**, chỉ đề xuất ở đây.
2. **Bỏ `policies` khỏi `schema.sql`?** Rulebook đang ở `shared/rulebook/*.json`
   (rule tree lồng nhau + provenance nhét vào cột SQL thì vẫn là JSON, thêm SQLite không được gì).
   Xem `docs/PROPOSAL-eligibility-2tang.md`.
3. **Ai sở hữu form?** `profiles` là bảng dùng chung; form là của server-b (Huy), engine đọc ở
   server-c (Hoàng). Đổi cột phải báo cả hai.
