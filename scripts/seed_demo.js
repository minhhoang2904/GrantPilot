// Run in MongoDB Shell (mongosh) or paste into MongoDB Atlas > Database > Browse Collections > mongosh
//
// mongosh "mongodb+srv://cluster0.lirx2mv.mongodb.net/grantpilot" --username grantpilot_db_user
// load("scripts/seed_demo.js")

db = db.getSiblingDB("grantpilot");

// Password: Demo@2024
// bcrypt hash generated offline — $2b$12$ prefix, 60 chars
const passwordHash = "$2b$12$O03KgUq56JXO17nzePlDN./21poUF31L6hk5evlMhalI2i1RLGYEO";

// ── Demo user ────────────────────────────────────────────────────────────────
db.users.updateOne(
  { email: "demo@grantpilot.vn" },
  {
    $set: {
      password_hash: passwordHash,
      updated_at: new Date()
    },
    $setOnInsert: {
      email: "demo@grantpilot.vn",
      created_at: new Date()
    }
  },
  { upsert: true }
);
print("[USER] demo@grantpilot.vn — ready");

// ── Demo company profile ─────────────────────────────────────────────────────
db.companies.updateOne(
  { email: "demo@grantpilot.vn" },
  {
    $set: {
      email: "demo@grantpilot.vn",
      company_name: "Công ty TNHH Thực phẩm Xanh Việt",
      profile_schema_version: "profile-v1",
      business_description: "Sản xuất và chế biến thực phẩm hữu cơ từ nguyên liệu nông sản địa phương. Chuyên cung cấp rau củ sấy, trà thảo mộc và gia vị hữu cơ cho thị trường nội địa.",
      province_name: "Hà Nội",
      province_code: "01",
      sector: "cong_nghiep_xay_dung",
      primary_business_activity_group: "processing",
      legal_form: "limited_liability_company",
      social_insurance_employees: 35,
      annual_revenue_vnd: 8000000000,
      total_capital_vnd: 3000000000,
      first_business_registration_date: "2021-03-15",
      has_public_offering: false,
      has_coworking_contract: true,
      has_business_registration: true,
      coworking_monthly_cost_vnd: 15000000,
      has_state_capital: false,
      has_foreign_investment_capital: false,
      has_collateral: true,
      has_received_same_interest_support: false,
      updated_at: new Date()
    },
    $setOnInsert: {
      created_at: new Date()
    }
  },
  { upsert: true }
);
print("[COMPANY] Công ty TNHH Thực phẩm Xanh Việt — ready");

print("");
print("==================================================");
print("  DEMO CREDENTIALS");
print("==================================================");
print("  Email:    demo@grantpilot.vn");
print("  Password: Demo@2024");
print("==================================================");
