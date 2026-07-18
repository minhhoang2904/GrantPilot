export type Sector =
  | 'nong_lam_ngu_nghiep'
  | 'cong_nghiep_xay_dung'
  | 'thuong_mai_dich_vu'

/** lookup = Tra cứu quy định/văn bản; advisory = Tư vấn theo hồ sơ doanh nghiệp */
export type ChatMode = 'lookup' | 'advisory'

export type BusinessActivityGroup =
  | 'agriculture'
  | 'forestry'
  | 'fisheries'
  | 'manufacturing'
  | 'processing'
  | 'construction'
  | 'trade'
  | 'services'
  | 'other'

export type LegalForm =
  | 'joint_stock_company'
  | 'limited_liability_company'
  | 'partnership'
  | 'private_enterprise'
  | 'cooperative'
  | 'household_business'
  | 'other'

export interface Company {
  email: string
  company_name: string
  profile_schema_version?: string

  // Identity/display context; policy rules do not read these fields.
  business_description?: string | null
  province_name?: string | null

  // Canonical Fact Catalog inputs.
  sector?: Sector | null
  primary_business_activity_group?: BusinessActivityGroup | null
  legal_form?: LegalForm | null
  province_code?: string | null
  social_insurance_employees?: number | null
  annual_revenue_vnd?: number | null
  total_capital_vnd?: number | null
  first_business_registration_date?: string | null
  has_public_offering?: boolean | null
  has_coworking_contract?: boolean | null
  has_business_registration?: boolean | null
  coworking_monthly_cost_vnd?: number | null
  has_state_capital?: boolean | null
  has_foreign_investment_capital?: boolean | null
  has_collateral?: boolean | null
  has_received_same_interest_support?: boolean | null
}

// ── Legacy types (old /ask API — kept for history backward compat) ─────────────

export interface PolicySource {
  dieu?: string
  khoan?: string
  thong_tu?: string
  url?: string
}

/** Legacy status values from old /ask endpoint */
export type PolicyStatus =
  | 'eligible'
  | 'partial'
  | 'not_eligible'
  | 'expired'
  | 'needs_more_information'
  | 'manual_review'

/** Legacy policy result from old /ask endpoint */
export interface PolicyResult {
  policy_id: string
  title: string
  status: PolicyStatus
  value?: number
  gap?: string[]
  roi_missed?: number
  source?: PolicySource
}

// ── New types (new /v1/chat/stream API) ───────────────────────────────────────

/** Eligibility status from the new streaming API */
export type EligibilityStatus =
  | 'eligible'
  | 'not_eligible'
  | 'needs_more_information'
  | 'manual_review'

/** Source citation item (from sources event in lookup mode) */
export interface SourceItem {
  unit_id: string
  document_number: string
  document_title: string
  article?: string
  clause?: string
  point?: string
  snippet?: string
  source_url?: string
  page_start?: number
  page_end?: number
}

/** Single policy assessment from advisory_result */
export interface AdvisoryPolicy {
  policy_id: string
  title: string
  status: EligibilityStatus
  score: number
  missing_fields: string[]
  reasons: string[]
  sources: SourceItem[]
}

export interface AdvisoryProfileFeatures {
  enterprise_size?: string
  is_sme?: boolean
  company_age_years?: number
}

/** Data payload from the advisory_result stream event */
export interface AdvisoryResult {
  explanation: string
  profile_features: AdvisoryProfileFeatures
  policies: AdvisoryPolicy[]
}

// ── Message (unified, covers both old and new API responses) ──────────────────

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  /** Legacy: eligibility results from old /ask API (kept for history rendering) */
  results?: PolicyResult[]
  /** New: source citations for lookup mode */
  sources?: SourceItem[]
  /** New: advisory assessment for advisory mode */
  advisoryResult?: AdvisoryResult
  /** Non-fatal warning from BE (e.g. ELIGIBILITY_UNAVAILABLE) */
  warning?: string
}

// ── Legacy response types (kept for old /ask endpoint) ───────────────────────

export interface AskResponse {
  answer: string
  results: PolicyResult[]
  session_id?: string
}

export interface FlatAskResponse {
  answer: string
}
