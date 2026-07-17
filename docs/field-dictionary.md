# Từ điển trường (Field Dictionary)

> ⚠️ Chốt ở kickoff. Đây là chỗ dễ lệch nhất giữa Thành (bóc rule) và Huy (form hồ sơ).
> Lệch tên trường → Engine không tìm thấy giá trị → trả `UNKNOWN` **âm thầm**, không crash.
>
> **Quy ước: tên trường bằng tiếng Anh, snake_case, không dấu.**

## Persona MVP
Startup phần mềm/công nghệ Việt Nam, ≤ 5 năm, hướng tới tư cách **DNNVV khởi nghiệp sáng tạo**
(Luật 04/2017/QH14 + Nghị định 80/2021/NĐ-CP).

---

## Trường hồ sơ doanh nghiệp

### Định danh & pháp lý
| Field | Kiểu | Giá trị hợp lệ | VD | Ghi chú |
|---|---|---|---|---|
| `company_name` | string | | "GreenVision AI" | chỉ hiển thị, không xét |
| `founded_year` | number | năm | 2023 | |
| `company_age_years` | number | năm | 2 | **dẫn xuất** = năm hiện tại − `founded_year`; tính từ ngày ĐKDN lần đầu |
| `legal_form` | string | `joint_stock` \| `llc` \| `partnership` \| `private` | "joint_stock" | |
| `is_public_offering` | boolean | | false | đã chào bán chứng khoán ra công chúng chưa |

### Địa bàn ⭐ mới
| Field | Kiểu | Giá trị hợp lệ | VD | Ghi chú |
|---|---|---|---|---|
| `province` | string | mã tỉnh snake_case (`hanoi`, `hcmc`, `da_nang`, `can_tho`, …) | "hanoi" | ⭐ **bắt buộc để xét tầng 2**. NĐ 80 triển khai qua UBND cấp tỉnh: mỗi tỉnh có chương trình, ngân sách, mức hỗ trợ và thời hạn riêng. `null` → `availability` không tra được → `UNKNOWN` → `NEED_MORE_INFO`. Xem `contracts.md` mục E2. |

> **Vì sao cần:** cùng một điều khoản trung ương, nhưng "chương trình có đang mở không / nộp ở đâu /
> mức hỗ trợ cụ thể bao nhiêu" là chuyện **của tỉnh**. Không có `province` thì `availability` mãi
> `unknown` và sản phẩm không trả lời được câu "tôi nộp ở đâu, còn kịp không".

### Quy mô (dùng để xác định DNNVV)
| Field | Kiểu | Đơn vị | VD | Ghi chú |
|---|---|---|---|---|
| `sector` | string | `information_technology` \| `manufacturing` \| `agriculture` \| `trade_service` | "information_technology" | ngưỡng DNNVV khác nhau theo lĩnh vực — map sang lĩnh vực của NĐ 80 ở `data/sme_classification.json` |
| `employee_count` | number | người | 18 | tổng nhân sự |
| `social_insurance_employees` | number | người | 18 | ⭐ số LĐ tham gia BHXH — đây mới là con số dùng để xét DNNVV |
| `annual_revenue_vnd` | number | VNĐ | 6000000000 | |
| `total_capital_vnd` | number | VNĐ | null | tổng nguồn vốn |
| `sme_size_category` | string | `sieu_nho` \| `nho` \| `vua` \| `khong_thuoc_dnnvv` | "nho" | ⭐ **dẫn xuất** — thay cho `is_sme` cũ. Do `src/eligibility/classifier.py` tra từ `data/sme_classification.json`. Xem "Trường dẫn xuất" bên dưới. |

> ⚠️ **`is_sme` (boolean) đã bỏ.** Lý do: một boolean không đủ — mức hỗ trợ trong NĐ 80 khác nhau
> theo hạng siêu nhỏ/nhỏ/vừa, nên `benefit` cần biết *hạng nào*, không chỉ *có phải DNNVV không*.
> Ai đang dùng `is_sme` → chuyển sang `sme_size_category in ["sieu_nho","nho","vua"]`.

### Chi phí thực tế của DN ⭐ mới — dùng để tính mức hỗ trợ
| Field | Kiểu | Đơn vị | Là `basis_field` của program | Ghi chú |
|---|---|---|---|---|
| `coworking_monthly_cost_vnd` | number | VNĐ/tháng | `coworking_rent_support` | chi phí thuê mặt bằng hằng tháng |
| `product_testing_cost_vnd` | number | VNĐ | `product_testing_support` | chi phí thử nghiệm/hoàn thiện sản phẩm |
| `ip_consulting_cost_vnd` | number | VNĐ | `ip_consulting_support` | chi phí tư vấn SHTT |
| `tech_transfer_cost_vnd` | number | VNĐ | `tech_transfer_support` | chi phí tư vấn/chuyển giao công nghệ |
| `training_cost_vnd` | number | VNĐ | `training_support` | học phí khóa đào tạo |
| `trade_promotion_cost_vnd` | number | VNĐ | `trade_promotion_support` | chi phí gian hàng/hội chợ |

> **Vì sao cần:** `benefit.type = "percentage_of_cost"` nghĩa là số tiền = `chi phí × rate`, áp trần.
> Trước đây `basis` chỉ là chuỗi mô tả cho người đọc ("chi phí thuê mặt bằng") — engine không có
> đường lấy con số. Kết quả: **kể cả khi đã điền đúng `rate` và `cap_amount` từ văn bản, vẫn không
> tính được tiền.** Nay mỗi program trỏ `benefit.basis_field` vào đúng một trường ở bảng này.
>
> Quy ước: chi phí **chưa khai → `null`** → `benefit_estimate.computable = false` với lý do
> "thiếu chi phí thực tế", và `missing_fields` chứa tên trường để chatbot hỏi lại.

### Tính đổi mới sáng tạo
| Field | Kiểu | Giá trị hợp lệ | VD | Ghi chú |
|---|---|---|---|---|
| `product_type` | string | `software` \| `mobile_app` \| `cloud` \| `ai` \| `platform` \| `hardware` \| `other` | "software" | |
| `has_patent` | boolean | | false | có bằng sáng chế/GPHI |
| `has_ip_registration` | boolean | | false | đã đăng ký SHTT |
| `is_innovative` | boolean | | null | ⚠️ `evaluation: human_review` — không tự kết luận được |

### Điều kiện loại trừ ⏳ chờ nguồn
| Field | Kiểu | VD | Trạng thái |
|---|---|---|---|
| `has_tax_debt` | boolean | null | ⏳ **chưa có rule dùng** — hỗ trợ từ NSNN thường yêu cầu không nợ thuế, nhưng chưa tìm được điều khoản cụ thể. Không có nguồn → không có rule. |
| `has_administrative_violation` | boolean | null | ⏳ **chưa có rule dùng** — chờ nguồn |

> ⚠️ **Không hỏi user những trường ⏳ này trong form** cho tới khi có rule thật dùng tới.
> Hỏi mà không dùng = làm phiền DN và tạo ảo giác sản phẩm chặt chẽ hơn thực tế.
> Khi Thành tìm được điều khoản → bỏ nhãn ⏳ → Huy mới thêm vào form.

### Lịch sử nhận hỗ trợ ⏳ chờ nguồn
| Field | Kiểu | VD | Trạng thái |
|---|---|---|---|
| `received_support_program_ids` | list[string] | `["training_support"]` | ⏳ đã từng nhận hỗ trợ nào. Dùng với toán tử `contains`/`not_contains`. Cần cho trần "không quá N lần" và cho `conflicts_with` **qua các năm**. |
| `received_support_amount_this_year_vnd` | number | null | ⏳ tổng đã nhận trong năm — cho trần tổng/năm nếu có |

> **Vì sao cần:** `conflicts_with` hiện chỉ chặn trùng lặp **trong một lần chạy**. Nếu DN đã nhận
> hỗ trợ đó năm ngoái, engine không biết. Ghi vào contract ngay để không ai thiết kế chặn đường,
> nhưng **chưa bật rule** cho tới khi có điều khoản thật.

### Hồ sơ/chứng từ (cho tầng 2)
| Field | Kiểu | VD | Dùng cho hỗ trợ |
|---|---|---|---|
| `has_coworking_contract` | boolean | null | thuê cơ sở ươm tạo / coworking |
| `has_business_registration` | boolean | true | mọi hỗ trợ |
| `has_financial_statement` | boolean | null | xác minh quy mô |

---

## Toán tử hỗ trợ

| Operator | Nghĩa | Kiểu |
|---|---|---|
| `==` | bằng | number/string/boolean |
| `!=` | khác | number/string/boolean |
| `<` `<=` `>` `>=` | so sánh | number |
| `in` | giá trị của DN thuộc danh sách `value` | string/number |
| `not_in` | không thuộc | string/number |
| `contains` ⭐ | **field của DN là list** và chứa `value` | list[string] |
| `not_contains` ⭐ | field là list và KHÔNG chứa `value` | list[string] |

> `in` vs `contains` — ngược chiều nhau, đừng nhầm:
> - `in`: DN có **một** giá trị, rule cho **danh sách** → `product_type in ["software","ai"]`
> - `contains`: DN có **danh sách**, rule cho **một** giá trị → `received_support_program_ids contains "training_support"`

Gộp nhóm: `all` (AND) · `any` (OR), lồng nhau tùy ý.

---

## Trường dẫn xuất

Trường không do user khai mà do hệ thống tính. **Phải ghi công thức ở đây**, và phải sinh được
trace + trích dẫn như rule thường (nếu không, ta lại giấu logic khỏi user — đúng thứ ta chê RAG phẳng).

| Field | Tính từ | Ai tính |
|---|---|---|
| `company_age_years` | năm hiện tại − `founded_year` | profile_builder |
| `sme_size_category` | `sector` + `social_insurance_employees` + (`annual_revenue_vnd` **hoặc** `total_capital_vnd`) | `src/eligibility/classifier.py` |

### `sme_size_category` — quy tắc tra
Bảng ngưỡng: `data/sme_classification.json` (nguồn: NĐ 80/2021 Điều 5 — **số liệu chưa điền**).

```
1. sector           → linh_vuc  (qua bảng sector_to_linh_vuc)
2. Với từng hạng theo thứ tự sieu_nho → nho → vua, hạng ĐẦU TIÊN thoả thì lấy:
       social_insurance_employees <= max_social_insurance_employees
   AND ( annual_revenue_vnd <= max_annual_revenue_vnd
         OR total_capital_vnd <= max_total_capital_vnd )      ← doanh thu HOẶC nguồn vốn
3. Không hạng nào thoả → "khong_thuoc_dnnvv"
```

Bốn giá trị (giống rule thường — `null` không bao giờ tự thành FAIL):
- `sector` là `null` → `UNKNOWN` (thiếu `sector`)
- `social_insurance_employees` là `null` → `UNKNOWN`
- **cả** `annual_revenue_vnd` **và** `total_capital_vnd` là `null` → `UNKNOWN`
  (chỉ cần một trong hai là tra được — vì luật dùng "hoặc")
- ngưỡng trong bảng còn `null` (chưa xác minh) → `UNKNOWN` + log "ngưỡng chưa xác minh",
  **KHÔNG** được coi là `khong_thuoc_dnnvv`

---

## Quy ước bắt buộc

1. **Chưa khai → `null`**, KHÔNG dùng `0`/`false`. Engine phân biệt "khai là không" vs "chưa khai".
   `null` → `UNKNOWN` → `NEED_MORE_INFO`, không bao giờ tự suy thành FAIL.
2. **Tiền**: số nguyên VNĐ, không dấu phân cách.
3. **Tỉ lệ**: thập phân (1% → `0.01`).
4. **Trường dẫn xuất**: tính từ trường gốc, ghi rõ công thức ở mục trên.
5. **Thêm field mới** → cập nhật bảng này TRƯỚC → báo cả đội → rồi mới dùng trong rule.
6. **Field ⏳ chờ nguồn**: được phép có trong từ điển, KHÔNG được đưa vào form và KHÔNG được
   có rule dùng tới, cho đến khi có `source_document` + `article` thật.
