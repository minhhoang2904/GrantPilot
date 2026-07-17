"""
benefit.py — Tính mức hỗ trợ ước tính. (chủ: Hoàng)

Xem docs/contracts.md mục E1.

--- NGUYÊN TẮC SỐ 1: KHÔNG BỊA SỐ ---
Thiếu bất kỳ mảnh nào → computable=False + note nói RÕ thiếu gì.
Thà nói "chưa tính được, cần xác minh" còn hơn đưa số sai. Giám khảo sẽ hỏi vặn đúng chỗ này,
và DN thật thì có thể mất tiền vì tin một con số bịa.

--- `note` PHẢI phân biệt AI phải làm gì tiếp ---
  "Chưa xác minh mức trần"      → ĐỘI phải đi đọc văn bản/hỏi cơ quan
  "DN chưa khai chi phí thuê"   → chatbot hỏi một câu là xong
Gộp cả hai thành "chưa đủ dữ liệu" là vứt đi thông tin đắt nhất với user.
"""

# Hạng hợp lệ để tra benefit.tiers. `khong_thuoc_dnnvv` và None đều không tra được.
VALID_TIERS = ("sieu_nho", "nho", "vua")


def _not_computable(note, tier_used=None, missing_fields=()):
    return {
        "computable": False,
        "amount_vnd": None,
        "tier_used": tier_used,
        "note": note,
        "missing_fields": list(missing_fields),
    }


def estimate(program, profile):
    """Ước tính mức hỗ trợ cho MỘT program. Trả BenefitEstimate (dict).

    {computable, amount_vnd, tier_used, note, missing_fields}
    """
    benefit = program.get("benefit") or {}
    btype = benefit.get("type")

    # --- Hỗ trợ bằng hiện vật: KHÔNG quy ra tiền ---
    # Suất đào tạo, gian hàng hội chợ... Quy đổi ra VNĐ là bịa số kiểu khác:
    # ta không biết cơ quan định giá suất đó bao nhiêu.
    if btype == "in_kind":
        return _not_computable(
            f"Hỗ trợ bằng hiện vật ({benefit.get('basis') or 'chưa mô tả'}) — không quy đổi ra tiền."
        )

    # --- Phải biết hạng DN mới tra được tier ---
    tier_key = profile.get("sme_size_category")
    if tier_key not in VALID_TIERS:
        reason = (
            "DN không thuộc diện DNNVV" if tier_key == "khong_thuoc_dnnvv"
            else "chưa xác định được hạng DN (siêu nhỏ/nhỏ/vừa)"
        )
        return _not_computable(f"Chưa tính được mức hỗ trợ: {reason}.")

    tier = (benefit.get("tiers") or {}).get(tier_key) or {}
    rate = tier.get("rate")
    cap = tier.get("cap_amount")

    if btype == "fixed_amount":
        if cap is None:
            return _not_computable(
                f"Chưa tính được: mức hỗ trợ cố định cho hạng {tier_key!r} chưa xác minh "
                f"từ văn bản gốc (việc của đội).",
                tier_used=tier_key,
            )
        return {
            "computable": True,
            "amount_vnd": int(cap),
            "tier_used": tier_key,
            "note": f"Mức cố định cho DN hạng {tier_key}.",
            "missing_fields": [],
        }

    if btype != "percentage_of_cost":
        return _not_computable(f"Loại hỗ trợ không nhận dạng được: {btype!r}.", tier_used=tier_key)

    # --- percentage_of_cost: tiền = chi phí × rate, áp trần ---
    # `basis` chỉ là chuỗi mô tả cho người đọc. `basis_field` mới là đường lấy SỐ.
    # Thiếu basis_field thì dù rate/cap đã điền đủ vẫn không bao giờ tính ra tiền.
    basis_field = benefit.get("basis_field")
    if not basis_field:
        return _not_computable(
            "Chưa tính được: program thiếu `basis_field` — không biết lấy chi phí thực tế "
            "từ trường nào của hồ sơ (lỗi data, việc của đội).",
            tier_used=tier_key,
        )

    # Hai lý do KHÁC NHAU, tách bạch — xem docstring đầu file.
    if rate is None or cap is None:
        thieu = []
        if rate is None:
            thieu.append("tỉ lệ hỗ trợ")
        if cap is None:
            thieu.append("mức trần")
        return _not_computable(
            f"Chưa tính được: {' và '.join(thieu)} cho hạng {tier_key!r} chưa xác minh "
            f"từ văn bản gốc (việc của đội, không hỏi DN được).",
            tier_used=tier_key,
        )

    actual_cost = profile.get(basis_field)
    if actual_cost is None:
        return _not_computable(
            f"Chưa tính được: DN chưa khai {benefit.get('basis') or basis_field}. "
            f"Khai xong là tính được ngay.",
            tier_used=tier_key,
            missing_fields=[basis_field],
        )

    raw = actual_cost * rate
    amount = min(raw, cap)
    capped = raw > cap

    period = benefit.get("cap_period") or "kỳ"
    duration = tier.get("max_duration_months")

    note = f"{int(rate * 100)}% × {actual_cost:,} = {int(raw):,}đ"
    note += f", vượt trần {cap:,}đ/{period} → lấy {int(amount):,}đ" if capped else f"/{period}"
    if duration:
        note += f". Tối đa {duration} tháng."
    note += " Ước tính sơ bộ, không phải cam kết cấp phát."

    return {
        "computable": True,
        "amount_vnd": int(amount),
        "tier_used": tier_key,
        "note": note,
        "missing_fields": [],
    }
