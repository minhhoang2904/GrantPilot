"""
classifier.py — Tra hạng DNNVV (TẦNG 0). (chủ: Hoàng) ⭐ mới

Xem docs/contracts.md mục B3 + docs/field-dictionary.md mục "Trường dẫn xuất".

classify_sme_size(profile, classification) -> SizeCategoryTrace
    Sinh trường dẫn xuất `profile.sme_size_category`, CHẠY TRƯỚC rule tầng 1.

--- VÌ SAO CẦN FILE NÀY (đừng xoá vì tưởng thừa) ---
Ngưỡng DNNVV KHÔNG phải một con số cố định — nó phụ thuộc LĨNH VỰC (NĐ 80 Điều 5).
Rule leaf chỉ có `value` scalar → không biểu diễn được "ngưỡng phụ thuộc ngành".
Viết bằng any[ all[sector==X, employees<=Y, ...] ] thì nổ tổ hợp (số lĩnh vực × số hạng ×
số tiêu chí) và mỗi nhánh phải lặp lại provenance → rất dễ lệch.

→ Tách ra: bảng tra (data/sme_classification.json) + trường dẫn xuất.
  Tầng 1 khi đó chỉ còn MỘT leaf sạch:  sme_size_category in [sieu_nho, nho, vua]

--- QUY TẮC TRA ---
  1. sector → linh_vuc            (qua classification["sector_to_linh_vuc"])
  2. Với từng hạng theo thứ tự sieu_nho → nho → vua, hạng ĐẦU TIÊN thoả thì lấy:
         social_insurance_employees <= max_social_insurance_employees
     AND ( annual_revenue_vnd <= max_annual_revenue_vnd
           OR total_capital_vnd <= max_total_capital_vnd )     ← luật dùng "HOẶC"
  3. Không hạng nào thoả → "khong_thuoc_dnnvv"

--- BỐN GIÁ TRỊ (giống rule thường — None không bao giờ tự thành FAIL) ---
Trả UNKNOWN khi:
  - profile.sector is None                       → thiếu sector
  - profile.social_insurance_employees is None   → thiếu số LĐ BHXH
  - CẢ HAI annual_revenue_vnd và total_capital_vnd is None
        (chỉ cần MỘT trong hai là tra được — vì luật dùng "hoặc")
  - sector_to_linh_vuc[sector] chưa map (còn "<TODO>")
  - ngưỡng trong bảng còn None (chưa xác minh)   → + log "ngưỡng chưa xác minh"

⚠️ Ngưỡng chưa xác minh → UNKNOWN, TUYỆT ĐỐI KHÔNG trả "khong_thuoc_dnnvv".
   Chưa biết ≠ không đạt. Đây đúng là lỗi mà cả kiến trúc này sinh ra để tránh.

--- BẮT BUỘC: SINH TRACE ---
Trả về SizeCategoryTrace có `trace` + `source` (trích dẫn Điều 5), để user hỏi
"vì sao tôi bị xếp hạng nhỏ" là trả lời được. Bảng tra KHÔNG được là hộp đen —
nếu giấu logic khỏi user thì ta đang làm đúng thứ ta chê RAG phẳng.

Trace mẫu:
  "Lĩnh vực <linh_vuc>; LĐ BHXH 18 ≤ <ngưỡng nhỏ>; doanh thu 6.000.000.000 ≤ <ngưỡng nhỏ>
   → hạng: nhỏ.  Căn cứ: Điều 5, Nghị định 80/2021/NĐ-CP"

--- KẾT QUẢ DÙNG Ở HAI CHỖ ---
  1. Tầng 1: rule `is_dnnvv` (sme_size_category in [...])
  2. benefit.py: tra `benefit.tiers[sme_size_category]` → rate/cap của ĐÚNG hạng đó
"""

from grantpilot.models.rule import RuleResult

# Thứ tự xét: hạng ĐẦU TIÊN thoả thì lấy (siêu nhỏ chặt hơn nhỏ, nhỏ chặt hơn vừa).
TIER_ORDER = ("sieu_nho", "nho", "vua")

NOT_SME = "khong_thuoc_dnnvv"

# Đầu vào của phép tra. Khi UNKNOWN, ĐÂY mới là thứ đáng hỏi user —
# không phải `sme_size_category` (user không khai được trường dẫn xuất).
INPUT_FIELDS = ("sector", "social_insurance_employees", "annual_revenue_vnd", "total_capital_vnd")


def _unknown(trace, source, missing_fields=()):
    return {
        "value": None,
        "result": RuleResult.UNKNOWN.value,
        "trace": trace,
        "source": source,
        "missing_fields": list(missing_fields),
    }


def classify_sme_size(profile, classification, ctx=None):
    """Tra hạng DNNVV. Trả SizeCategoryTrace: {value, result, trace, source, missing_fields}.

    `ctx` (EvalContext) chỉ để gom warnings — truyền None nếu không cần.
    """
    source = (f"{classification.get('article') or '<chưa có điều khoản>'}, "
              f"{classification.get('source_document') or '<chưa có văn bản>'}")

    # --- 1. sector → lĩnh vực của NĐ 80 ---
    # NĐ 80 chia theo lĩnh vực của LUẬT, không theo `sector` do đội tự định nghĩa.
    # Map sai ở đây thì toàn bộ tầng 1 sai theo, mà lại sai im lặng.
    sector = profile.get("sector")
    if sector is None:
        return _unknown("Chưa khai lĩnh vực (sector) → không tra được ngưỡng.", source, ["sector"])

    linh_vuc = (classification.get("sector_to_linh_vuc") or {}).get(sector)
    if not linh_vuc or str(linh_vuc).startswith("<TODO"):
        msg = f"Chưa xác minh map lĩnh vực cho sector={sector!r} (sector_to_linh_vuc còn trống)."
        if ctx is not None:
            ctx.warnings.append(f"classifier: {msg}")
        return _unknown(msg, source)

    criteria = (classification.get("criteria") or {}).get(linh_vuc)
    if not criteria:
        msg = f"Bảng ngưỡng thiếu lĩnh vực {linh_vuc!r}."
        if ctx is not None:
            ctx.warnings.append(f"classifier: {msg}")
        return _unknown(msg, source)

    # --- 2. Đầu vào của DN ---
    employees = profile.get("social_insurance_employees")
    revenue = profile.get("annual_revenue_vnd")
    capital = profile.get("total_capital_vnd")

    if employees is None:
        return _unknown(
            "Chưa khai số lao động tham gia BHXH → không tra được hạng.",
            source, ["social_insurance_employees"],
        )

    # Luật dùng "doanh thu HOẶC nguồn vốn" → chỉ cần MỘT trong hai.
    # Thiếu cả hai mới là thiếu thật; hỏi cả hai khi user đã khai một cái là làm phiền vô ích.
    if revenue is None and capital is None:
        return _unknown(
            "Chưa khai doanh thu năm lẫn tổng nguồn vốn "
            "(luật xét doanh thu HOẶC nguồn vốn — chỉ cần một).",
            source, ["annual_revenue_vnd", "total_capital_vnd"],
        )

    # --- 3. Duyệt từng hạng, hạng đầu tiên thoả thì lấy ---
    for tier in TIER_ORDER:
        t = criteria.get(tier) or {}
        max_emp = t.get("max_social_insurance_employees")
        max_rev = t.get("max_annual_revenue_vnd")
        max_cap = t.get("max_total_capital_vnd")

        # Ngưỡng chưa xác minh → DỪNG HẲN, trả UNKNOWN.
        # Không được "bỏ qua hạng này rồi xét hạng sau": bỏ qua sẽ đẩy DN xuống hạng thấp hơn
        # hoặc rơi ra khong_thuoc_dnnvv — tức là bịa kết luận từ ô trống.
        if max_emp is None or (max_rev is None and max_cap is None):
            msg = (f"Ngưỡng hạng {tier!r} của lĩnh vực {linh_vuc!r} chưa xác minh "
                   f"(còn null trong sme_classification.json).")
            if ctx is not None:
                ctx.warnings.append(f"classifier: {msg}")
            return _unknown(msg, source)

        emp_ok = employees <= max_emp
        rev_ok = revenue is not None and max_rev is not None and revenue <= max_rev
        cap_ok = capital is not None and max_cap is not None and capital <= max_cap

        if emp_ok and (rev_ok or cap_ok):
            which, amount, limit = (
                ("doanh thu", revenue, max_rev) if rev_ok else ("nguồn vốn", capital, max_cap)
            )
            return {
                "value": tier,
                "result": RuleResult.PASS.value,
                "trace": (f"Lĩnh vực {linh_vuc}; LĐ BHXH {employees} ≤ {max_emp}; "
                          f"{which} {amount:,} ≤ {limit:,} → hạng {tier}."),
                "source": source,
                "missing_fields": [],
            }

    # Không hạng nào thoả → vượt ngưỡng DNNVV.
    # Đây là kết luận THẬT (PASS), không phải UNKNOWN: ta đã tra đủ và biết chắc DN nằm ngoài.
    # Rule `is_dnnvv` ở tầng 1 sẽ FAIL trên giá trị này.
    return {
        "value": NOT_SME,
        "result": RuleResult.PASS.value,
        "trace": (f"Lĩnh vực {linh_vuc}; LĐ BHXH {employees} và quy mô tài chính "
                  f"vượt mọi ngưỡng DNNVV → không thuộc diện."),
        "source": source,
        "missing_fields": [],
    }
