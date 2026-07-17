export type Sector =
  | 'nong_lam_ngu_nghiep'
  | 'cong_nghiep_xay_dung'
  | 'thuong_mai_dich_vu'

export interface Company {
  email: string
  company_name: string

  // tầng 0: phân hạng DNNVV
  sector?: Sector | null
  social_insurance_employees?: number | null
  annual_revenue_vnd?: number | null
  total_capital_vnd?: number | null

  // tầng 1: tư cách
  founded_year?: number | null
  is_public_offering?: boolean | null
  product_type?: string | null
  has_patent?: boolean | null

  // địa bàn
  province?: string | null

  // tầng 2: hồ sơ chứng từ
  has_coworking_contract?: boolean | null
  has_business_registration?: boolean | null

  // chi phí thực tế
  coworking_monthly_cost_vnd?: number | null
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
  value?: number
  gap?: string[]
  roi_missed?: number
  source?: PolicySource
}

export interface AskResponse {
  answer: string
  results: PolicyResult[]
}

export interface FlatAskResponse {
  answer: string
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  results?: PolicyResult[]
}
