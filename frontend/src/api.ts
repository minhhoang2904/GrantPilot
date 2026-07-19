import type { AskResponse, Company, FlatAskResponse, ChatMode } from './types'
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

export async function updateCompany(
  email: string,
  payload: Partial<Omit<Company, 'email'>>,
): Promise<Company> {
  const result = await request<Company>('PATCH', `/companies/${encodeURIComponent(email)}`, payload)
  if (!result) throw new ApiError(404, 'Không tìm thấy hồ sơ công ty.')
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

export async function deleteSession(email: string, sessionId: string): Promise<void> {
  const result = await request<{ status: string }>(
    'DELETE',
    `/history/${encodeURIComponent(email)}/sessions/${encodeURIComponent(sessionId)}`,
  )
  if (!result) throw new ApiError(404, 'Không tìm thấy phiên chat.')
}

type RawAskResponse = {
  answer: string
  results?: AskResponse['results']
  policies?: AskResponse['results']
  session_id?: string
}

function normalizeAskResponse(raw: RawAskResponse): AskResponse {
  return {
    answer: raw.answer,
    results: raw.results ?? raw.policies ?? [],
    session_id: raw.session_id,
  }
}

export async function ask(
  email: string,
  question: string,
  sessionId?: string,
  mode: ChatMode = 'rag',
): Promise<AskResponse> {
  const result = await request<RawAskResponse>('POST', '/ask', {
    email,
    question,
    session_id: sessionId ?? null,
    mode,
  })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return normalizeAskResponse(result)
}

type AskStreamEvent =
  | { type: 'status'; message: string }
  | { type: 'delta'; text: string }
  | { type: 'done'; results?: AskResponse['results']; session_id?: string }
  | { type: 'error'; message: string }

export async function askStream(
  email: string,
  question: string,
  sessionId: string | undefined,
  mode: ChatMode,
  onDelta: (text: string) => void,
): Promise<AskResponse> {
  const res = await fetch(`${BASE}/ask/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({
      email,
      question,
      session_id: sessionId ?? null,
      mode,
    }),
  })
  if (res.status === 401) {
    clearSession()
    window.location.reload()
    throw new ApiError(401, 'Phiên đăng nhập đã hết hạn.')
  }
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, `Server lỗi ${res.status}: ${text}`)
  }
  if (!res.body) throw new ApiError(500, 'Trình duyệt không hỗ trợ phản hồi streaming.')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let answer = ''
  let doneEvent: Extract<AskStreamEvent, { type: 'done' }> | undefined

  function consumeLine(line: string) {
    if (!line.trim()) return
    const event = JSON.parse(line) as AskStreamEvent
    if (event.type === 'delta') {
      answer += event.text
      onDelta(event.text)
    } else if (event.type === 'done') {
      doneEvent = event
    } else if (event.type === 'error') {
      throw new ApiError(500, event.message)
    }
  }

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''
    for (const line of lines) consumeLine(line)
    if (done) break
  }
  if (buffer) consumeLine(buffer)
  if (!doneEvent) throw new ApiError(500, 'Luồng phản hồi kết thúc không hợp lệ.')

  return {
    answer,
    results: doneEvent.results ?? [],
    session_id: doneEvent.session_id,
  }
}

export async function askFlat(question: string): Promise<FlatAskResponse> {
  const result = await request<FlatAskResponse>('POST', '/ask/flat', { question })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return result
}
