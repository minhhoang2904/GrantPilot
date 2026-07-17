import type { AskResponse, Company, FlatAskResponse } from './types'
import { getToken, clearSession } from './auth'

// In dev, Vite proxies /api/* -> http://localhost:8001/* (see vite.config.ts).
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

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T | null> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      ...(body ? { 'Content-Type': 'application/json' } : {}),
      ...authHeaders(),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 404) return null
  if (res.status === 401) {
    // Token expired or invalid — clear session and reload to login
    clearSession()
    window.location.reload()
    return null
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, `Server lỗi ${res.status}: ${text}`)
  }
  return res.json() as Promise<T>
}

// ── Auth ──────────────────────────────────────────────────────────────────────

export async function apiRegister(email: string, password: string): Promise<{ token: string; email: string }> {
  const result = await fetch(`${BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await result.json()
  if (!result.ok) throw new ApiError(result.status, data.detail ?? 'Đăng ký thất bại.')
  return data
}

export async function apiLogin(email: string, password: string): Promise<{ token: string; email: string }> {
  const result = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  const data = await result.json()
  if (!result.ok) throw new ApiError(result.status, data.detail ?? 'Đăng nhập thất bại.')
  return data
}

// ── Company ───────────────────────────────────────────────────────────────────

export async function getCompany(email: string): Promise<Company | null> {
  return request<Company>('GET', `/companies/${encodeURIComponent(email)}`)
}

export async function createCompany(payload: Omit<Company, never>): Promise<Company> {
  const result = await request<Company>('POST', '/companies', payload)
  if (!result) throw new ApiError(500, 'Không tạo được hồ sơ công ty.')
  return result
}

// ── Chat ──────────────────────────────────────────────────────────────────────

export interface HistoryTurn {
  role: 'user' | 'assistant'
  content: string
  results?: unknown[]
  ts: string
}

export interface HistorySession {
  session_id: string
  started_at: string
  turns: HistoryTurn[]
}

export async function getHistory(email: string): Promise<HistorySession[]> {
  const result = await request<HistorySession[]>('GET', `/history/${encodeURIComponent(email)}`)
  return result ?? []
}

export async function ask(
  email: string,
  question: string,
  sessionId?: string,
): Promise<AskResponse> {
  const result = await request<AskResponse>('POST', '/ask', {
    email,
    question,
    session_id: sessionId ?? null,
  })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return result
}

export async function askFlat(question: string): Promise<FlatAskResponse> {
  const result = await request<FlatAskResponse>('POST', '/ask/flat', { question })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return result
}
