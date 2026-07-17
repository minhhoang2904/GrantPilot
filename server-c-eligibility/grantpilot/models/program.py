"""
Schema `program` — TẦNG 2: một loại hỗ trợ. Xem docs/contracts.md mục E.

Tương ứng data/programs.json. MVP có 6 program (thuê coworking, thử nghiệm SP,
tư vấn SHTT, chuyển giao công nghệ, đào tạo, xúc tiến thương mại).

⚠️ data/programs.json nay là OBJECT BỌC, không phải mảng trần:
      { "ruleset_version": "0.1.0-draft", "programs": [ <Program>, ... ] }
   Loader phải đọc key "programs". Đổi để mang được version (xem eligibility_result.py).

  class RequiredDocument:
      doc_id: str
      name: str                    # "Hợp đồng thuê mặt bằng"
      profile_field: str           # trường boolean trong profile để check

  class BenefitTier:
      rate: float | None           # VD 0.5 = hỗ trợ 50%
      cap_amount: int | None       # mức trần VNĐ
      max_duration_months: int | None

  class Benefit:
      type: str                    # "percentage_of_cost" | "fixed_amount" | "in_kind"
      basis: str                   # mô tả cho người đọc: "chi phí thuê mặt bằng"
      basis_field: str | None      # ⭐ trỏ vào ĐÚNG MỘT trường chi phí trong profile
                                   #    (VD "coworking_monthly_cost_vnd") — đây là đường
                                   #    engine lấy con số. Thiếu nó thì percentage_of_cost
                                   #    không bao giờ tính được, dù rate/cap đã điền đủ.
      cap_period: str | None       # "month" | "year" | "contract"
      tiers: dict[str, BenefitTier]  # ⭐ LUÔN đủ 3 key: "sieu_nho" | "nho" | "vua"
                                   #    tra bằng profile.sme_size_category
      note: str

      # ⚠️ computable=False khi thiếu BẤT KỲ thứ nào:
      #      - sme_size_category là UNKNOWN/khong_thuoc_dnnvv  → không biết tra tier nào
      #      - tiers[hạng].rate hoặc .cap_amount là None       → chưa xác minh
      #      - profile[basis_field] là None                     → thiếu chi phí thực tế
      #    type="in_kind" → LUÔN computable=False, note mô tả hiện vật. KHÔNG quy ra tiền.

  class ProvinceAvailability:
      status: str                  # "open" | "closed" | "unknown"
      local_program_code: str|None # mã chương trình của tỉnh (nếu có)
      deadline: str | None         # ISO date — hạn của tỉnh, THẮNG submission.deadline
      note: str

  class Availability:
      scope: str                          # "province"
      by_province: dict[str, ProvinceAvailability]
      default: ProvinceAvailability       # dùng khi tỉnh không có trong by_province

      # ⭐ Tra theo profile.province:
      #      province is None            → UNKNOWN → NEED_MORE_INFO + missing_fields "province"
      #      by_province[province] có     → dùng
      #      không có                     → dùng default
      #    status "unknown"/"closed" → PROGRAM_UNAVAILABLE (Case 5)
      #
      # Vì sao theo tỉnh: NĐ 80 triển khai qua UBND cấp tỉnh — chương trình, ngân sách,
      # mức hỗ trợ, thời hạn đều là chuyện của tỉnh. Availability toàn cục thì mãi "unknown".

  class SubmissionForm:
      form_id: str
      name: str
      url: str

  class Submission:
      agency: str | None           # cơ quan tiếp nhận (CHUYỂN từ Program.agency vào đây)
      where: str | None            # địa chỉ / cổng dịch vụ công
      forms: list[SubmissionForm]
      processing_time_days: int|None  # "bao lâu có kết quả"
      deadline: str | None         # ISO date — hạn chung; hạn theo tỉnh thắng
      note: str | None
      # Trả lời câu "rồi sao nữa?" — không có khối này thì sản phẩm im lặng
      # đúng lúc DN sẵn sàng hành động nhất.

  class Program:
      program_id: str
      name: str
      requires_qualification: str  # trỏ về tầng 1
      rules: RuleNode              # điều kiện RIÊNG của hỗ trợ này
      required_documents: list[RequiredDocument]
      benefit: Benefit
      availability: Availability
      submission: Submission
      conflicts_with: list[str]    # program_id xung khắc → cảnh báo + không cộng trùng
      source_document: str
      article: str
      source_url: str
      review_status: str
      effective_from: str | None   # ISO date
      effective_to: str | None     # None = còn hiệu lực

MIGRATION so với bản trước:
  - program.agency            → program.submission.agency
  - benefit.rate/cap_amount/max_duration_months (phẳng) → benefit.tiers[hạng].*
  - benefit thêm basis_field
  - availability.status (phẳng) → availability.by_province / .default
  - thêm effective_from / effective_to
"""

# TODO: Pydantic BaseModel
