export interface Company {
  email: string
  ten_doanh_nghiep: string
  linh_vuc?: string
  tuoi?: number
  so_lao_dong?: number
  ty_le_rnd?: number
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
