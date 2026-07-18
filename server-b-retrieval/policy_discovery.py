"""Query-scoped policy discovery for the approved MVP policy set.

This is product routing metadata, not company facts and not a replacement for
the ingestion Fact Catalog.  Server C remains the only decision layer.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Literal


INFORMATION_POLICY_ID = "decree_80_2021_nd_cp_ho_tro_thong_tin_a26213ed"
ONLINE_TRAINING_POLICY_ID = "decree_80_2021_nd_cp_hd_dao_tao_truc_tuyen_d470ff1d"
IN_PERSON_TRAINING_POLICY_ID = "decree_80_2021_nd_cp_hd_dao_tao_truc_tiep_d470ff1d"
DIGITAL_TRANSFORMATION_POLICY_ID = "circular_06_2022_tt_bkhdt_ho_tro_cong_nghe_48284a5c"

GOLDEN_POLICY_IDS = (
    INFORMATION_POLICY_ID,
    ONLINE_TRAINING_POLICY_ID,
    IN_PERSON_TRAINING_POLICY_ID,
    DIGITAL_TRANSFORMATION_POLICY_ID,
)

CoverageStatus = Literal[
    "supported", "partial_coverage", "not_covered", "profile_scan"
]


@dataclass(frozen=True)
class DiscoveryResult:
    coverage_status: CoverageStatus
    policy_ids: tuple[str, ...]
    matched_topics: tuple[str, ...] = ()
    unsupported_topics: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        return {
            "coverage_status": self.coverage_status,
            "policy_ids": list(self.policy_ids),
            "matched_topics": list(self.matched_topics),
            "unsupported_topics": list(self.unsupported_topics),
        }


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _folded(text: str) -> str:
    text = unicodedata.normalize("NFD", _normalized(text))
    text = "".join(character for character in text if unicodedata.category(character) != "Mn")
    text = text.replace("đ", "d")
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    padded = f" {text} "
    return any(f" {phrase} " in padded for phrase in phrases)


_SUPPORTED_TOPICS = (
    (
        "hỗ trợ thông tin cho DNNVV",
        (INFORMATION_POLICY_ID,),
        (
            "ho tro thong tin",
            "thong tin cho doanh nghiep",
            "cong thong tin doanh nghiep",
            "tra cuu thong tin ho tro",
        ),
    ),
    (
        "đào tạo khởi sự và quản trị doanh nghiệp",
        (ONLINE_TRAINING_POLICY_ID, IN_PERSON_TRAINING_POLICY_ID),
        (
            "dao tao",
            "khoa hoc",
            "khoi su kinh doanh",
            "quan tri doanh nghiep",
            "phat trien nguon nhan luc",
            "tap huan",
        ),
    ),
    (
        "thuê hoặc mua giải pháp chuyển đổi số",
        (DIGITAL_TRANSFORMATION_POLICY_ID,),
        (
            "chuyen doi so",
            "giai phap so",
            "giai phap chuyen doi",
            "thue hoac mua giai phap",
            "mua giai phap chuyen doi so",
            "ho tro cong nghe",
            "cong nghe va chuyen doi so",
        ),
    ),
)

_UNSUPPORTED_TOPICS = (
    (
        "ưu đãi thuế thu nhập doanh nghiệp (TNDN)",
        (
            "thuế tndn",
            "thuế thu nhập doanh nghiệp",
            "ưu đãi thuế",
            "miễn giảm thuế",
            "miễn thuế",
            "giảm thuế",
        ),
        (
            "thue tndn",
            "thue thu nhap doanh nghiep",
            "uu dai thue",
            "mien giam thue",
            "mien thue",
            "giam thue",
        ),
    ),
    (
        "Quỹ Đổi mới công nghệ quốc gia (NATIF)",
        ("natif", "quỹ đổi mới công nghệ quốc gia"),
        ("natif", "quy doi moi cong nghe quoc gia"),
    ),
)

_PROFILE_SCAN_PHRASES = (
    "chinh sach nao",
    "duoc ho tro gi",
    "duoc huong gi",
    "phu hop voi doanh nghiep",
    "quet ho so",
    "danh gia ho so",
    "tat ca chinh sach",
    "cong ty toi co duoc ho tro khong",
    "doanh nghiep toi co duoc ho tro khong",
    "tu van cho doanh nghiep",
)


def discover_policies(
    question: str,
    retrieved_policy_ids: list[str] | tuple[str, ...] = (),
) -> DiscoveryResult:
    """Return only approved MVP policies relevant to the user's intent."""
    normalized = _normalized(question)
    folded = _folded(question)

    matched_topics: list[str] = []
    selected: set[str] = set()
    for label, policy_ids, keywords in _SUPPORTED_TOPICS:
        if _contains_any(folded, keywords):
            matched_topics.append(label)
            selected.update(policy_ids)

    unsupported_topics: list[str] = []
    for label, normalized_phrases, folded_phrases in _UNSUPPORTED_TOPICS:
        if _contains_any(normalized, normalized_phrases) or _contains_any(folded, folded_phrases):
            unsupported_topics.append(label)

    if selected:
        ordered = tuple(policy_id for policy_id in GOLDEN_POLICY_IDS if policy_id in selected)
        status: CoverageStatus = "partial_coverage" if unsupported_topics else "supported"
        return DiscoveryResult(status, ordered, tuple(matched_topics), tuple(unsupported_topics))

    if unsupported_topics:
        return DiscoveryResult("not_covered", (), (), tuple(unsupported_topics))

    if _contains_any(folded, _PROFILE_SCAN_PHRASES):
        return DiscoveryResult(
            "profile_scan",
            GOLDEN_POLICY_IDS,
            ("toàn bộ chính sách trong bộ MVP",),
        )

    retrieved = set(retrieved_policy_ids)
    fallback_ids = tuple(policy_id for policy_id in GOLDEN_POLICY_IDS if policy_id in retrieved)
    if fallback_ids:
        return DiscoveryResult(
            "supported",
            fallback_ids,
            ("chính sách phù hợp được tìm thấy",),
        )

    return DiscoveryResult("not_covered", (), (), ("nội dung bạn đang hỏi",))
