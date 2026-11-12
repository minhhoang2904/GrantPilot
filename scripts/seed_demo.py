"""Seed a demo user + company profile for showcase.

Usage:
    python scripts/seed_demo.py

Creates (or resets) a demo account with a realistic Vietnamese SME profile
that triggers multiple eligibility policies. Prints login credentials
when done.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Load .env from project root
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

try:
    import bcrypt
    from pymongo import MongoClient
except ImportError:
    sys.exit("Missing packages. Run: pip install bcrypt pymongo[srv] dnspython")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
MONGODB_DB = os.getenv("MONGODB_DATABASE", os.getenv("MONGODB_DB", "grantpilot")).strip()

DEMO_EMAIL = "demo@grantpilot.vn"
DEMO_PASSWORD = "Demo@2024"

DEMO_COMPANY = {
    "email": DEMO_EMAIL,
    "company_name": "Công ty TNHH Thực phẩm Xanh Việt",
    "profile_schema_version": "profile-v1",
    "business_description": (
        "Sản xuất và chế biến thực phẩm hữu cơ từ nguyên liệu nông sản địa phương. "
        "Chuyên cung cấp rau củ sấy, trà thảo mộc và gia vị hữu cơ cho thị trường nội địa."
    ),
    "province_name": "Hà Nội",
    "province_code": "01",
    "sector": "cong_nghiep_xay_dung",
    "primary_business_activity_group": "processing",
    "legal_form": "limited_liability_company",
    "social_insurance_employees": 35,
    "annual_revenue_vnd": 8_000_000_000,
    "total_capital_vnd": 3_000_000_000,
    "first_business_registration_date": "2021-03-15",
    "has_public_offering": False,
    "has_coworking_contract": True,
    "has_business_registration": True,
    "coworking_monthly_cost_vnd": 15_000_000,
    "has_state_capital": False,
    "has_foreign_investment_capital": False,
    "has_collateral": True,
    "has_received_same_interest_support": False,
}

# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def main() -> None:
    if not MONGODB_URI:
        sys.exit("MONGODB_URI not set. Check your .env file.")

    client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB]

    # ── User ──────────────────────────────────────────────────────────────
    users = db["users"]
    users.create_index("email", unique=True)
    password_hash = bcrypt.hashpw(DEMO_PASSWORD.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc)

    users.update_one(
        {"email": DEMO_EMAIL},
        {
            "$set": {"password_hash": password_hash, "updated_at": now},
            "$setOnInsert": {"email": DEMO_EMAIL, "created_at": now},
        },
        upsert=True,
    )
    print(f"[USER] {DEMO_EMAIL} — ready")

    # ── Company profile ───────────────────────────────────────────────────
    companies = db["companies"]
    companies.create_index("email", unique=True)

    companies.update_one(
        {"email": DEMO_EMAIL},
        {
            "$set": {**DEMO_COMPANY, "updated_at": now},
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )
    print(f"[COMPANY] {DEMO_COMPANY['company_name']} — ready")

    client.close()

    # ── Print credentials ─────────────────────────────────────────────────
    print()
    print("=" * 50)
    print("  DEMO CREDENTIALS")
    print("=" * 50)
    print(f"  Email:    {DEMO_EMAIL}")
    print(f"  Password: {DEMO_PASSWORD}")
    print("=" * 50)
    print()
    print("Company profile:")
    print(f"  Name:       {DEMO_COMPANY['company_name']}")
    print(f"  Sector:     Công nghiệp — Chế biến")
    print(f"  Legal form: Công ty TNHH")
    print(f"  Employees:  {DEMO_COMPANY['social_insurance_employees']}")
    print(f"  Revenue:    {DEMO_COMPANY['annual_revenue_vnd']:,.0f} VND/year")
    print(f"  Capital:    {DEMO_COMPANY['total_capital_vnd']:,.0f} VND")
    print(f"  Province:   {DEMO_COMPANY['province_name']}")
    print(f"  Registered: {DEMO_COMPANY['first_business_registration_date']}")


if __name__ == "__main__":
    main()
