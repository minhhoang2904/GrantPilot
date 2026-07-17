"""
Schema `profile` — hồ sơ doanh nghiệp. Xem docs/contracts.md mục F + field-dictionary.md.

Chủ: Huy tạo (form / LLM bóc từ lời kể) → Hoàng dùng để xét.

⚠️ QUY TẮC SỐNG CÒN:
  - Tên trường PHẢI khớp `field` trong Condition (rule.py).
  - Trường chưa khai để None — KHÔNG dùng 0/false.
    Engine phân biệt "khai là không" (false) với "chưa khai" (None → UNKNOWN → NEED_MORE_INFO).

  class Profile:
      # định danh & pháp lý
      company_name: str
      founded_year: int | None
      company_age_years: int | None          # dẫn xuất = năm nay - founded_year
      legal_form: str | None                 # joint_stock | llc | partnership | private
      is_public_offering: bool | None

      # địa bàn ⭐ mới
      province: str | None                   # "hanoi" | "hcmc" | ... — mã tỉnh snake_case
                                             # ⭐ bắt buộc để tra availability: NĐ 80 triển khai qua
                                             # UBND cấp tỉnh, mỗi tỉnh có chương trình/ngân sách/hạn riêng.
                                             # None → UNKNOWN → NEED_MORE_INFO, missing_fields += ["province"]

      # quy mô (xét DNNVV)
      sector: str | None                     # information_technology | manufacturing | ...
      employee_count: int | None
      social_insurance_employees: int | None  # ⭐ con số dùng xét DNNVV
      annual_revenue_vnd: int | None
      total_capital_vnd: int | None
      sme_size_category: str | None          # sieu_nho | nho | vua | khong_thuoc_dnnvv
                                             # ⭐ DẪN XUẤT — classifier.py điền, user KHÔNG khai

      # chi phí thực tế ⭐ mới — là `basis_field` của benefit.
      # Không có nhóm này thì percentage_of_cost KHÔNG BAO GIỜ tính ra tiền, dù đã điền đủ rate/cap.
      coworking_monthly_cost_vnd: int | None
      product_testing_cost_vnd: int | None
      ip_consulting_cost_vnd: int | None
      tech_transfer_cost_vnd: int | None
      training_cost_vnd: int | None
      trade_promotion_cost_vnd: int | None

      # tính đổi mới
      product_type: str | None               # software | mobile_app | cloud | ai | ...
      has_patent: bool | None
      has_ip_registration: bool | None
      is_innovative: bool | None             # evaluation: human_review

      # hồ sơ/chứng từ (tầng 2)
      has_coworking_contract: bool | None
      has_business_registration: bool | None
      has_financial_statement: bool | None

      # ⏳ chờ nguồn — CÓ trong schema, nhưng KHÔNG đưa vào form và KHÔNG rule nào dùng
      #    cho tới khi có source_document + article thật. Xem field-dictionary.md.
      has_tax_debt: bool | None
      has_administrative_violation: bool | None
      received_support_program_ids: list[str] | None   # dùng với operator contains/not_contains
      received_support_amount_this_year_vnd: int | None

⚠️ `is_sme: bool` ĐÃ BỎ → thay bằng `sme_size_category`.
   Lý do: benefit.tiers cần biết HẠNG nào (mức hỗ trợ khác nhau theo siêu nhỏ/nhỏ/vừa),
   một boolean không mang đủ thông tin. Ai còn dùng is_sme → đổi sang
   `sme_size_category in ["sieu_nho","nho","vua"]` (chính là rule `is_dnnvv` ở tầng 1).
"""

# TODO: Pydantic BaseModel — mọi field Optional, default None
