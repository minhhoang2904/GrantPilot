export type Sector =
  | 'nong_lam_ngu_nghiep'
  | 'cong_nghiep_xay_dung'
  | 'thuong_mai_dich_vu'

/** rag = Tra cứu nhanh (default); eligibility = Tư vấn sâu theo hồ sơ DN */
export type ChatMode = 'rag' | 'eligibility'

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

export interface PolicySource {
  dieu?: string
  khoan?: string
  thong_tu?: string
  url?: string
}

export type PolicyStatus = 'eligible' | 'partial' | 'not_eligible' | 'expired'

export interface PolicyResult {
  policy_id: string
  title: string
  status: PolicyStatus
  gap?: string[]
  roi_missed?: number
  source?: PolicySource
}

export interface AskResponse {
  answer: string
  results: PolicyResult[]
  session_id?: string
}

export interface FlatAskResponse {
  answer: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  results?: PolicyResult[]
  streaming?: boolean
}
