import type { AskResponse, Company, FlatAskResponse } from './types'

// In dev, Vite proxies /api/* -> http://localhost:8001/* (see vite.config.ts).
// In production, requests go to the same origin (nginx proxies) or VITE_SERVER_B_URL.
const BASE = '/api'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T | null> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 404) return null
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, `Server B lỗi ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

export async function getCompany(email: string): Promise<Company | null> {
  return request<Company>('GET', `/companies/${encodeURIComponent(email)}`)
}

export async function createCompany(payload: Omit<Company, never>): Promise<Company> {
  const result = await request<Company>('POST', '/companies', payload)
  if (!result) throw new ApiError(500, 'Không tạo được hồ sơ công ty.')
  return result
}

export async function ask(email: string, question: string): Promise<AskResponse> {
  const result = await request<AskResponse>('POST', '/ask', { email, question })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return result
}

export async function askFlat(question: string): Promise<FlatAskResponse> {
  const result = await request<FlatAskResponse>('POST', '/ask/flat', { question })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return result
}
