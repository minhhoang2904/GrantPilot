"""
Schema `qualification` — TẦNG 1: tư cách gốc. Xem docs/contracts.md mục D.

Tương ứng data/qualification.json. Chỉ có MỘT bộ trong MVP:
"DNNVV khởi nghiệp sáng tạo" (Luật 04/2017/QH14 + Nghị định 80/2021/NĐ-CP).

Không đạt tầng này → mọi program tầng 2 tự động tắt.

  class Qualification:
      ruleset_version: str         # ⭐ semver, tăng mỗi lần đổi rule/ngưỡng
                                   #    → ghi vào EligibilityResult để tái lập kết luận cũ
      qualification_id: str        # "dnnvv_khoi_nghiep_sang_tao"
      name: str
      description: str
      source_documents: list[str]
      rules: RuleNode              # cây điều kiện (xem rule.py)

--- ĐỔI so với bản trước ---
Cụm rule ngưỡng DNNVV lồng nhau (LĐ BHXH + any[doanh thu | nguồn vốn]) đã được thay bằng
MỘT leaf duy nhất:

    { "rule_id": "is_dnnvv", "field": "sme_size_category",
      "operator": "in", "value": ["sieu_nho", "nho", "vua"], ... }

Ngưỡng thật nằm ở data/sme_classification.json, do classifier.py tra ra `sme_size_category`
TRƯỚC khi rule tầng 1 chạy. Xem contracts.md mục B3.
"""

# TODO: Pydantic BaseModel
