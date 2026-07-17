# Contracts — "Hiến pháp" của dự án

Định nghĩa schema bằng code: `src/models/`. Từ điển trường: `field-dictionary.md`.

## Luật bất di bất dịch

> **Không có nguồn → không có rule.** Mọi điều kiện phải trỏ được về điều/khoản của văn bản thật.
> **LLM không quyết định eligibility.** LLM chỉ bóc rule (có người review) và diễn giải kết quả.

---

# A. MÔ HÌNH HAI TẦNG

```
TẦNG 0 — PHÂN HẠNG (sme_classification.json)   ← trường dẫn xuất, không phải rule
  sector + LĐ BHXH + (doanh thu | nguồn vốn) → sme_size_category
        │
        ▼
TẦNG 1 — TƯ CÁCH (qualification.json)
  "DN có phải DNNVV khởi nghiệp sáng tạo không?"
  1 bộ rule duy nhất. Không đạt → mọi hỗ trợ tầng 2 đều tắt.
        │
        ▼
TẦNG 2 — TỪNG HỖ TRỢ (programs.json)
  6 loại hỗ trợ, mỗi loại có: rule riêng + hồ sơ riêng + mức trần riêng (theo hạng) + availability theo tỉnh
```

Nhờ tách tầng, ta trả lời được: *"Bạn **thuộc diện** DNNVV KNST ✅, nhưng để nhận hỗ trợ thuê
coworking thì **còn thiếu hợp đồng thuê**"* — đây là Case 4.

> **Tầng 0 không phải một tầng rule mới.** Nó là bước tra bảng sinh ra trường dẫn xuất
> `sme_size_category` trước khi rule tầng 1 chạy. Xem mục B3.

---

# B. SCHEMA `rule` — điều kiện (dùng chung cả 2 tầng)

Một **rule tree** gồm 2 loại node:

## B1. Leaf — một điều kiện cụ thể

```json
{
  "rule_id": "startup_age_limit",
  "field": "company_age_years",
  "operator": "<=",
  "value": 5,

  "description": "Thành lập không quá 5 năm",
  "hard": true,
  "evaluation": "auto",

  "source_document": "Luật 04/2017/QH14",
  "article": "Điều 17, Khoản 1, Điểm a",
  "source_url": "https://...",
  "interpretation_note": "Tính từ ngày cấp đăng ký doanh nghiệp lần đầu",
  "review_status": "manually_reviewed",
  "effective_from": "2018-01-01",
  "effective_to": null
}
```

| Trường | Vai trò |
|---|---|
| `rule_id` | 🔑 định danh rule, dùng để trace |
| `field` | tên trường DN — PHẢI có trong `field-dictionary.md` |
| `operator` | `==` `!=` `<` `<=` `>` `>=` `in` `not_in` `contains` `not_contains` |
| `value` | ngưỡng so sánh |
| `description` | diễn giải tiếng người (hiển thị cho user) |
| `hard` | `true` = không khắc phục được (tuổi) → gap analysis báo vô vọng; `false` = cải thiện được |
| `evaluation` | `auto` = máy xét được; `human_review` = cần người/cơ quan xác minh (VD "có tính đổi mới sáng tạo") |
| `source_document` / `article` / `source_url` | ⭐ **provenance — bắt buộc**, không có thì rule không được dùng |
| `interpretation_note` | cách đội hiểu điều khoản này (để review chéo và để chuyên gia soi) |
| `review_status` | `draft` → `manually_reviewed` (2 người đồng ý) → `expert_reviewed`. Chỉ `manually_reviewed` trở lên mới được bật trong demo. |
| `effective_from` / `effective_to` ⭐ | hiệu lực của điều khoản (ISO `YYYY-MM-DD`). `effective_to: null` = còn hiệu lực. |

### Vì sao cần `effective_from` / `effective_to`
Văn bản pháp luật được sửa đổi, thay thế, hết hiệu lực. Không có mốc thời gian thì:
- Không biết kết luận hôm nay dựa trên bản nào.
- Kết luận lưu tháng trước không tái lập được → DN mang đi thuyết trình mà bị hỏi vặn thì không đỡ được.

Engine bỏ qua rule không còn hiệu lực tại `evaluated_at` **và ghi log**, không im lặng.
Rule bị bỏ vì hết hiệu lực phải hiện trong `warnings`, không được biến mất âm thầm.

## B2. Group — gộp nhiều điều kiện

```json
{ "all": [ <node>, <node>, ... ] }     // AND — mọi node phải đạt
{ "any": [ <node>, <node>, ... ] }     // OR  — chỉ cần một node đạt
```

Group lồng nhau tùy ý. Ví dụ thật:

```json
{
  "all": [
    { "rule_id": "is_dnnvv", "field": "sme_size_category", "operator": "in",
      "value": ["sieu_nho","nho","vua"], "...": "..." },
    { "rule_id": "startup_age_limit", "field": "company_age_years", "operator": "<=", "value": 5, "...": "..." },
    { "any": [
        { "rule_id": "innovative_product", "field": "product_type", "operator": "in", "value": ["software","mobile_app","cloud","ai"], "...": "..." },
        { "rule_id": "has_patent", "field": "has_patent", "operator": "==", "value": true, "...": "..." }
    ]}
  ]
}
```

## B3. Trường dẫn xuất & bảng tra ⭐ (tầng 0)

Có điều kiện **không biểu diễn được bằng một leaf** vì ngưỡng phụ thuộc trường khác.
Ví dụ điển hình: ngưỡng DNNVV phụ thuộc **lĩnh vực** (NĐ 80 Điều 5).

Cách xử lý: **tra bảng trước, rule sau.**

```
data/sme_classification.json  →  src/eligibility/classifier.py  →  profile.sme_size_category
                                                                            │
                                                    rule tầng 1 chỉ còn 1 leaf sạch:
                                                    sme_size_category in [sieu_nho, nho, vua]
```

Ràng buộc bắt buộc với mọi bảng tra:
1. **Có provenance như rule thường** — `source_document` + `article` + `source_url` + `review_status`.
2. **Sinh trace** — classifier phải trả lời được "vì sao tôi bị xếp hạng nhỏ", kèm trích dẫn.
   Không được là hộp đen; nếu giấu logic khỏi user thì ta đang làm đúng thứ ta chê RAG phẳng.
3. **Bốn giá trị** — thiếu dữ liệu đầu vào hoặc ngưỡng chưa xác minh → `UNKNOWN`,
   **không bao giờ** tự suy thành `khong_thuoc_dnnvv`.

Quy tắc tra cụ thể: xem `field-dictionary.md` mục "Trường dẫn xuất".

---

# C. LOGIC BỐN GIÁ TRỊ ⭐ (trái tim engine)

Mỗi leaf KHÔNG trả true/false, mà trả **một trong bốn**:

| Kết quả | Khi nào |
|---|---|
| `PASS` | so sánh đúng |
| `FAIL` | so sánh sai |
| `UNKNOWN` | profile thiếu trường này → chưa kết luận được |
| `NEEDS_REVIEW` | leaf có `evaluation: "human_review"` → máy không tự quyết |

**Cách gộp lên group** (thứ tự ưu tiên, trên thắng dưới):

```
all (AND):  FAIL  >  UNKNOWN  >  NEEDS_REVIEW  >  PASS
any (OR) :  PASS  >  UNKNOWN  >  NEEDS_REVIEW  >  FAIL
```

Giải thích lựa chọn:
- **`all`: FAIL thắng tất cả** — một điều kiện cứng trượt thì thiếu dữ liệu chỗ khác cũng vô nghĩa.
  → Đây chính là Case 3: DN 7 tuổi → `NOT_ELIGIBLE` ngay, dù chưa khai doanh thu.
- **UNKNOWN trên NEEDS_REVIEW** — hỏi user là bước rẻ nhất; chỉ escalate lên người khi user đã khai hết.
- **`any`: PASS thắng** — một nhánh đạt là đủ, khỏi xét nhánh còn lại.

---

# D. SCHEMA `qualification` (Tầng 1)

File: `data/qualification.json`

```json
{
  "ruleset_version": "0.1.0-draft",
  "qualification_id": "dnnvv_khoi_nghiep_sang_tao",
  "name": "DNNVV khởi nghiệp sáng tạo",
  "description": "Tư cách gốc để tiếp cận các hỗ trợ theo Nghị định 80/2021/NĐ-CP",
  "source_documents": ["Luật 04/2017/QH14", "Nghị định 80/2021/NĐ-CP"],
  "rules": { "all": [ ... ] }
}
```

`ruleset_version` — semver, tăng mỗi lần đổi rule/ngưỡng. Ghi vào `eligibility_result` để
tái lập được kết luận cũ. Xem mục G.

---

# E. SCHEMA `program` (Tầng 2)

File: `data/programs.json` — **object bọc** `{ ruleset_version, programs: [...] }`
(trước đây là mảng trần; đổi để mang được version — xem mục G).

```json
{
  "program_id": "coworking_rent_support",
  "name": "Hỗ trợ thuê cơ sở ươm tạo / khu làm việc chung",

  "requires_qualification": "dnnvv_khoi_nghiep_sang_tao",
  "rules": { "all": [ ... ] },

  "required_documents": [
    { "doc_id": "lease_contract", "name": "Hợp đồng thuê mặt bằng", "profile_field": "has_coworking_contract" }
  ],

  "benefit": { ... },        // mục E1
  "availability": { ... },   // mục E2
  "submission": { ... },     // mục E3

  "conflicts_with": [],

  "source_document": "Nghị định 80/2021/NĐ-CP",
  "article": "<Điều ...>",
  "source_url": "https://...",
  "review_status": "draft",
  "effective_from": "<TODO>",
  "effective_to": null
}
```

| Khối | Vai trò |
|---|---|
| `requires_qualification` | trỏ về tầng 1 — không đạt tư cách thì program tự động tắt |
| `rules` | điều kiện RIÊNG của hỗ trợ này |
| `required_documents` | hồ sơ cần → thiếu thì `NEED_MORE_INFO` + checklist (Case 4) |
| `benefit` | ⭐ mức hỗ trợ theo hạng DN. **Thiếu số → không tính, báo rõ lý do** |
| `availability` | chương trình có đang mở **tại tỉnh của DN** không (Case 5) |
| `submission` | nộp ở đâu, cho ai, hạn nào, bao lâu — trả lời "rồi sao nữa?" |
| `conflicts_with` | program không được hưởng đồng thời → cảnh báo + KHÔNG cộng trùng (Case 6) |

## E1. `benefit` — mức hỗ trợ ⭐ đổi nhiều

```json
"benefit": {
  "type": "percentage_of_cost",
  "basis": "chi phí thuê mặt bằng tại cơ sở ươm tạo/khu làm việc chung",
  "basis_field": "coworking_monthly_cost_vnd",
  "cap_period": "month",
  "tiers": {
    "sieu_nho": { "rate": null, "cap_amount": null, "max_duration_months": null },
    "nho":      { "rate": null, "cap_amount": null, "max_duration_months": null },
    "vua":      { "rate": null, "cap_amount": null, "max_duration_months": null }
  },
  "note": "CHƯA ĐIỀN — lấy đúng tỉ lệ/mức trần/thời hạn từ NĐ 80/2021. Không đoán."
}
```

| Trường | Vai trò |
|---|---|
| `type` | `percentage_of_cost` \| `fixed_amount` \| `in_kind` (hỗ trợ bằng hiện vật: suất đào tạo, gian hàng — không quy ra tiền) |
| `basis` | mô tả cho người đọc |
| `basis_field` ⭐ | **trỏ vào đúng một trường chi phí** trong `field-dictionary.md`. Đây là đường engine lấy con số. |
| `cap_period` | `month` \| `year` \| `contract` |
| `tiers` ⭐ | **luôn có đủ 3 hạng** `sieu_nho`/`nho`/`vua`, mỗi hạng có `rate`/`cap_amount`/`max_duration_months` |

### Vì sao `basis_field` (gap nghiêm trọng nhất)
`percentage_of_cost` nghĩa là *tiền = chi phí × rate*, áp trần. Trước đây `basis` chỉ là **chuỗi mô tả**
— engine không có đường lấy "chi phí". Hệ quả: kể cả khi Thành điền xong `rate` và `cap_amount`,
`computable` vẫn `false` **vĩnh viễn**. Câu hỏi đắt nhất của DN ("tôi được bao nhiêu tiền?") không
có đường trả lời. `basis_field` là dây nối còn thiếu.

### Vì sao `tiers` thay cho `rate` phẳng
Mức hỗ trợ trong NĐ 80 khác nhau theo hạng DN, nhưng schema cũ chỉ có **một** `rate`.
Một rate phẳng → hoặc sai cho 2/3 số DN, hoặc buộc phải chọn bừa một hạng.

**Luôn điền đủ 3 hạng, kể cả khi giống nhau.** Hơi thừa, nhưng buộc Thành *xác nhận có chủ đích*
rằng "văn bản thật sự không phân biệt hạng", thay vì im lặng giả định. Đúng tinh thần review chéo.

### Quy tắc tính (chi tiết ở `src/eligibility/benefit.py`)
`computable = false` + ghi rõ lý do khi thiếu **bất kỳ** thứ nào:
- `sme_size_category` là `UNKNOWN`/`khong_thuoc_dnnvv` → không biết tra tier nào
- `tiers[hạng].rate` hoặc `.cap_amount` là `null` → chưa xác minh
- `profile[basis_field]` là `null` → thiếu chi phí thực tế → đưa vào `missing_fields`

`type: "in_kind"` → luôn `computable: false`, `note` mô tả hiện vật. **Không quy đổi ra tiền.**

## E2. `availability` — theo tỉnh ⭐ mới

```json
"availability": {
  "scope": "province",
  "by_province": {
    "hanoi": { "status": "unknown", "local_program_code": null, "deadline": null, "note": "<TODO>" }
  },
  "default": { "status": "unknown", "note": "Chưa xác minh chương trình tại tỉnh này" }
}
```

| `status` | Nghĩa |
|---|---|
| `open` | đã xác minh đang nhận hồ sơ tại tỉnh này |
| `closed` | đã đóng / hết hạn → loại, kèm cảnh báo (Case 6) |
| `unknown` | chưa xác minh → `PROGRAM_UNAVAILABLE` (Case 5) |

Cách tra:
```
profile.province is None        → UNKNOWN → NEED_MORE_INFO, missing_fields += ["province"]
by_province[province] tồn tại   → dùng
không tồn tại                   → dùng `default`
```

### Vì sao theo tỉnh
NĐ 80 triển khai qua UBND cấp tỉnh: **chương trình, ngân sách, mức hỗ trợ, thời hạn là chuyện của tỉnh**.
Cùng một điều khoản trung ương, startup ở Cần Thơ và ở Hà Nội có kết quả khác nhau.
`availability` toàn cục thì mãi `unknown` → mọi program đều `PROGRAM_UNAVAILABLE` → sản phẩm
không trả lời được gì. Xem thêm "Rủi ro lát cắt dọc" ở `data/README.md`.

## E3. `submission` — nộp ở đâu ⭐ mới

```json
"submission": {
  "agency": "<TODO: cơ quan tiếp nhận>",
  "where": "<TODO: địa chỉ / cổng dịch vụ công>",
  "forms": [ { "form_id": "<TODO>", "name": "<TODO>", "url": "<TODO>" } ],
  "processing_time_days": null,
  "deadline": null,
  "note": "<TODO>"
}
```

`agency` **chuyển từ top-level của Program vào đây** (migration: `program.agency` → `program.submission.agency`).

### Vì sao
DN đọc xong `LIKELY_ELIGIBLE` sẽ hỏi ngay "rồi sao nữa?". Không có khối này thì sản phẩm im lặng
đúng lúc DN sẵn sàng hành động nhất. `deadline` trả lời "còn kịp không";
`processing_time_days` trả lời "bao lâu có kết quả" — hai câu quyết định DN có bỏ công làm hồ sơ hay không.

> `deadline` ở đây là hạn chung của program. Hạn **theo tỉnh** nằm ở `availability.by_province[].deadline`
> và **thắng** khi cả hai cùng có.

---

# F. SCHEMA `profile` — hồ sơ doanh nghiệp

**Ai:** Huy tạo (form / LLM bóc từ lời kể) → Hoàng dùng.

```json
{
  "company_name": "GreenVision AI",
  "province": "hanoi",
  "founded_year": 2023,
  "company_age_years": 2,
  "legal_form": "joint_stock",
  "sector": "information_technology",
  "product_type": "software",
  "employee_count": 18,
  "social_insurance_employees": 18,
  "annual_revenue_vnd": 6000000000,
  "total_capital_vnd": null,
  "sme_size_category": null,
  "is_public_offering": false,
  "has_patent": false,
  "has_ip_registration": false,
  "has_coworking_contract": null,
  "coworking_monthly_cost_vnd": null
}
```

⚠️ Trường chưa khai để `null` — KHÔNG để 0 hay false. Engine phân biệt "khai là không"
với "chưa khai": `null` → `UNKNOWN` → `NEED_MORE_INFO` (Case 2).

⚠️ `is_sme` (boolean) **đã bỏ** → thay bằng `sme_size_category` (enum, dẫn xuất — mục B3).
`sme_size_category` do classifier điền, **user không khai**.

Danh sách trường đầy đủ: `field-dictionary.md`.

---

# G. SCHEMA `eligibility_result` — kết quả

**Ai:** Hoàng tạo → Huy (LLM diễn giải) + UI.

## 5 trạng thái

| Status | Nghĩa | Hành động của user |
|---|---|---|
| `LIKELY_ELIGIBLE` | Có khả năng đủ điều kiện | Chuẩn bị hồ sơ nộp |
| `NOT_ELIGIBLE` | Có điều kiện rõ ràng không đạt | Xem hỗ trợ khác |
| `NEED_MORE_INFO` | Thiếu dữ liệu **hoặc thiếu hồ sơ chứng minh** → chưa kết luận | Khai thêm / bổ sung giấy tờ |
| `NEEDS_HUMAN_REVIEW` | Điều kiện cần chuyên gia/cơ quan xác minh | Liên hệ cơ quan |
| `PROGRAM_UNAVAILABLE` | Có căn cứ pháp lý nhưng chưa rõ chương trình đang mở tại tỉnh | Xác minh với cơ quan |

> `NEED_MORE_INFO` bao gồm cả trường hợp thiếu hồ sơ (không tách `NEEDS_DOCUMENTS` riêng),
> nhưng `missing_documents` được liệt kê riêng để UI hiện checklist.

```json
{
  "program_id": "coworking_rent_support",
  "program_name": "Hỗ trợ thuê khu làm việc chung",
  "status": "NEED_MORE_INFO",
  "legal_status": "NEED_MORE_INFO",

  "evaluated_at": "2026-07-17T10:30:00+07:00",
  "ruleset_version": "0.1.0-draft",

  "qualification": {
    "qualification_id": "dnnvv_khoi_nghiep_sang_tao",
    "status": "LIKELY_ELIGIBLE",
    "passed": 4, "total": 4,
    "sme_size_category": {
      "value": "nho",
      "result": "PASS",
      "trace": "Lĩnh vực <linh_vuc>; LĐ BHXH 18 ≤ <ngưỡng>; doanh thu 6.000.000.000 ≤ <ngưỡng> → hạng nhỏ.",
      "source": "Điều 5, Nghị định 80/2021/NĐ-CP",
      "missing_fields": []
    }
  },

  "passed": 2, "total": 3,
  "conditions": [
    { "rule_id": "startup_age_limit", "description": "Thành lập không quá 5 năm",
      "result": "PASS", "current_value": "2 năm", "hard": true,
      "source": "Điều 17 Khoản 1 Điểm a, Luật 04/2017/QH14" },
    { "rule_id": "revenue_declared", "description": "Doanh thu năm",
      "result": "UNKNOWN", "current_value": null, "hard": false,
      "missing_field": "annual_revenue_vnd",
      "source": "..." }
  ],

  "missing_fields": ["coworking_monthly_cost_vnd"],
  "missing_documents": [
    { "doc_id": "lease_contract", "name": "Hợp đồng thuê mặt bằng" }
  ],

  "fixable": true,
  "blocking_reason": null,

  "benefit_estimate": {
    "computable": false,
    "amount_vnd": null,
    "tier_used": null,
    "note": "Chưa tính được: DN chưa khai chi phí thuê mặt bằng. Khai xong là tính được ngay.",
    "missing_fields": ["coworking_monthly_cost_vnd"]
  },

  "submission": { "agency": "...", "deadline": null, "processing_time_days": null },

  "warnings": ["Xung khắc với program X — chỉ được chọn một"]
}
```

| Trường | Vai trò |
|---|---|
| `status` | ⭐ 1 trong 5 trạng thái — `legal_status` đã phủ `availability` |
| `legal_status` ⭐ | 1 trong 4 (không bao giờ `PROGRAM_UNAVAILABLE`) — chỉ từ rule + hồ sơ |
| `evaluated_at` ⭐ | thời điểm xét (ISO 8601) — dùng để lọc rule theo hiệu lực |
| `ruleset_version` ⭐ | phiên bản bộ rule đã dùng |
| `qualification` | kết quả tầng 1 (gộp vào để giải thích "vì sao tắt") + trace phân hạng |
| `conditions` | từng điều kiện: PASS/FAIL/UNKNOWN/NEEDS_REVIEW + giá trị hiện tại + **nguồn trích dẫn** |
| `missing_fields` | trường user chưa khai → chatbot hỏi lại đúng field (Case 2) |
| `missing_documents` | hồ sơ thiếu → checklist (Case 4) |
| `fixable` | mọi điều kiện trượt đều `hard: false`? |
| `blocking_reason` | nếu `NOT_ELIGIBLE`: điều kiện cứng nào chặn (Case 3) |
| `benefit_estimate` | `computable: false` khi chưa rõ mức trần/chu kỳ/chi phí → **không bịa số**. `tier_used` ghi hạng đã tra. `missing_fields` = trường chi phí user cần khai để tính được (engine gộp lên `result.missing_fields`). |
| `submission` | copy từ program → UI hiện "bước tiếp theo" ngay cạnh kết quả |
| `warnings` | xung khắc / hết hiệu lực / rule bị bỏ |

### Vì sao tách `status` và `legal_status` ⭐
`availability` là **lớp phủ, không phải cửa chặn**. Engine luôn xét hết rule, rồi mới phủ:

| `legal_status` | `availability` | → `status` |
|---|---|---|
| `LIKELY_ELIGIBLE` | `open` | `LIKELY_ELIGIBLE` |
| `LIKELY_ELIGIBLE` | `unknown` | `PROGRAM_UNAVAILABLE` |
| `NOT_ELIGIBLE` | `unknown` | `PROGRAM_UNAVAILABLE` |

Hai dòng đầu **là cả nghiệp vụ của sản phẩm**: *đủ điều kiện pháp lý ≠ chắc chắn được cấp tiền*.
Chỉ có một trường `status` thì mất luôn vế đầu — UI không nói được câu quan trọng nhất:
*"bạn thuộc diện ✅, nhưng chương trình ở tỉnh bạn chưa xác minh đang mở"*.

Đây cũng là thứ gỡ mâu thuẫn Case 1 vs Case 5: hai case dùng **cùng hồ sơ**, khác nhau ở **tỉnh**,
không phải ở rule. Engine tất định thì cùng input không thể ra hai status khác nhau — trước đây
hai case này không thể cùng PASS.

### Vì sao `evaluated_at` + `ruleset_version`
Hai trường này biến kết quả từ "một câu trả lời" thành **một kết luận tái lập được**:
DN in ra mang đi họp, 3 tháng sau bị hỏi "căn cứ đâu, lúc đó luật thế nào" — không có chúng thì
không ai trả lời được, kể cả chính đội. Đây cũng là điều kiện cần để sau này audit được engine.
