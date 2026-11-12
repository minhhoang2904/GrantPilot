-- Schema dùng chung cho shared/policy.db (SQLite)
-- Nguồn duy nhất cho cấu trúc DB. Mọi thay đổi phải qua PR review chung.

CREATE TABLE IF NOT EXISTS policies (
    id                    TEXT PRIMARY KEY,
    title                 TEXT NOT NULL,
    summary               TEXT,
    content               TEXT,
    category              TEXT,
    issuing_agency        TEXT,
    effective_date        TEXT,
    source_url            TEXT,
    eligibility_criteria  TEXT,               -- JSON: điều kiện hưởng (dùng bởi server-c)
    created_at            TEXT DEFAULT (datetime('now')),
    updated_at            TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS profiles (
    id                          TEXT PRIMARY KEY,
    company_name                TEXT,      -- chỉ hiển thị, không rule nào đọc

    -- tầng 0: phân hạng DNNVV
    sector                      TEXT,      -- enum: nong_lam_ngu_nghiep | cong_nghiep_xay_dung | thuong_mai_dich_vu
    social_insurance_employees  INTEGER,   -- ⚠️ BHXH, KHÔNG phải tổng nhân sự
    annual_revenue_vnd          INTEGER,   -- ⚠️ INTEGER, không REAL
    total_capital_vnd           INTEGER,   -- doanh thu HOẶC nguồn vốn, chỉ cần một

    -- tầng 1: tư cách
    founded_year                INTEGER,   -- ⚠️ lưu NĂM, không lưu số tuổi
    is_public_offering          INTEGER,   -- 0/1/NULL
    product_type                TEXT,
    has_patent                  INTEGER,   -- 0/1/NULL

    -- địa bàn: tra availability
    province                    TEXT,

    -- tầng 2: hồ sơ chứng từ
    has_coworking_contract      INTEGER,   -- 0/1/NULL
    has_business_registration   INTEGER,   -- 0/1/NULL

    -- chi phí thực tế: để tính tiền (thêm dần theo program Thành điền)
    coworking_monthly_cost_vnd  INTEGER,

    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS eligibility_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id   TEXT NOT NULL,
    policy_id    TEXT NOT NULL,
    is_eligible  INTEGER NOT NULL,            -- 0/1
    score        REAL,                        -- dùng để ranking
    reasons      TEXT,                        -- JSON: danh sách lý do đạt/không đạt
    created_at   TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (profile_id) REFERENCES profiles(id),
    FOREIGN KEY (policy_id) REFERENCES policies(id)
);

CREATE INDEX IF NOT EXISTS idx_policies_category ON policies(category);
CREATE INDEX IF NOT EXISTS idx_eligibility_profile ON eligibility_results(profile_id);
CREATE INDEX IF NOT EXISTS idx_eligibility_policy ON eligibility_results(policy_id);
