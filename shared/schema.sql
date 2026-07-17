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
    id                TEXT PRIMARY KEY,
    business_name     TEXT,
    industry          TEXT,
    business_type     TEXT,                  -- vd: ho_kinh_doanh, doanh_nghiep_nho, sme, startup...
    num_employees     INTEGER,
    province          TEXT,
    annual_revenue    REAL,
    founded_year      INTEGER,
    extra_attributes  TEXT,                  -- JSON: thuộc tính bổ sung, linh hoạt theo policy
    created_at        TEXT DEFAULT (datetime('now')),
    updated_at        TEXT DEFAULT (datetime('now'))
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
