"""Seed five deterministic company profiles for demo and eligibility mock cases."""

from profile_service import upsert_profile

PROFILES = [
    {
        "id": "mock-finsight-ai-2022",
        "business_name": "FinSight AI",
        "industry": "Công nghệ tài chính (AI/SaaS)",
        "business_type": "startup",
        "num_employees": 18,
        "province": "Hà Nội",
        "annual_revenue": 3_200_000_000,
        "founded_year": 2022,
        "extra_attributes": {"is_sme": True, "is_innovative_startup": True, "has_rnd": True, "needs": ["vốn", "ươm tạo", "sở hữu trí tuệ"]},
    },
    {
        "id": "mock-greentech-manufacturing-2018",
        "business_name": "GreenTech Components",
        "industry": "Sản xuất thiết bị tiết kiệm năng lượng",
        "business_type": "doanh_nghiep_nho",
        "num_employees": 72,
        "province": "Đà Nẵng",
        "annual_revenue": 28_000_000_000,
        "founded_year": 2018,
        "extra_attributes": {"is_sme": True, "is_innovative_startup": False, "has_rnd": True, "needs": ["đổi mới công nghệ", "đào tạo", "tín dụng"]},
    },
    {
        "id": "mock-agriconnect-2023",
        "business_name": "AgriConnect Mekong",
        "industry": "Nền tảng công nghệ nông nghiệp",
        "business_type": "startup",
        "num_employees": 9,
        "province": "Cần Thơ",
        "annual_revenue": 850_000_000,
        "founded_year": 2023,
        "extra_attributes": {"is_sme": True, "is_innovative_startup": True, "has_rnd": False, "needs": ["chuyển đổi số", "thị trường", "vốn"]},
    },
    {
        "id": "mock-medvision-2020",
        "business_name": "MedVision Diagnostics",
        "industry": "Công nghệ y tế",
        "business_type": "sme",
        "num_employees": 45,
        "province": "TP. Hồ Chí Minh",
        "annual_revenue": 12_500_000_000,
        "founded_year": 2020,
        "extra_attributes": {"is_sme": True, "is_innovative_startup": True, "has_rnd": True, "has_ip_assets": True, "needs": ["sở hữu trí tuệ", "công nghệ", "tín dụng"]},
    },
    {
        "id": "mock-bigcommerce-2012",
        "business_name": "BigCommerce Việt Nam",
        "industry": "Thương mại điện tử",
        "business_type": "doanh_nghiep_lon",
        "num_employees": 420,
        "province": "Bình Dương",
        "annual_revenue": 650_000_000_000,
        "founded_year": 2012,
        "extra_attributes": {"is_sme": False, "is_innovative_startup": False, "has_rnd": False, "needs": ["mở rộng thị trường"]},
    },
]


def main() -> None:
    for profile in PROFILES:
        upsert_profile(profile)
    print(f"Seeded {len(PROFILES)} mock profiles into MongoDB")


if __name__ == "__main__":
    main()
