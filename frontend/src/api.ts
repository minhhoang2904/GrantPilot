import type {
  AdvisoryResult,
  AskResponse,
  ChatMode,
  Company,
  FlatAskResponse,
  SourceItem,
} from './types'
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

// ── Chat history ──────────────────────────────────────────────────────────────

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

// ── New streaming chat API (/v1/chat/stream) ──────────────────────────────────

type StartedEvent = {
  type: 'started'
  request_id: string
  conversation_id: string
  mode: ChatMode
}

type AnswerDeltaEvent = {
  type: 'answer_delta'
  text: string
}

type SourcesEvent = {
  type: 'sources'
  items: SourceItem[]
}

type AdvisoryResultEvent = {
  type: 'advisory_result'
  data: AdvisoryResult
}

type CompletedEvent = {
  type: 'completed'
  message_id: string
}

type ErrorEvent = {
  type: 'error'
  error: {
    code: string
    message: string
    retryable: boolean
  }
}

type WarningEvent = {
  type: 'warning'
  code: string
  message: string
}

export type ChatStreamEvent =
  | StartedEvent
  | AnswerDeltaEvent
  | SourcesEvent
  | AdvisoryResultEvent
  | CompletedEvent
  | ErrorEvent
  | WarningEvent

export async function* chatStream(
  message: string,
  mode: ChatMode,
  conversationId: string | null,
): AsyncGenerator<ChatStreamEvent> {
  const res = await fetch(`${BASE}/v1/chat/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/x-ndjson',
      ...authHeaders(),
    },
    body: JSON.stringify({
      mode,
      message,
      conversation_id: conversationId,
      options: { top_k: 5 },
    }),
  })

  if (res.status === 401) {
    clearSession()
    window.location.reload()
    return
  }

  if (res.status === 409) {
    throw new ApiError(409, 'Cần hồ sơ doanh nghiệp để dùng chế độ tư vấn.')
  }

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, `Server lỗi ${res.status}: ${text}`)
  }

  if (!res.body) {
    throw new ApiError(500, 'Không nhận được phản hồi từ server.')
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed) {
          try {
            yield JSON.parse(trimmed) as ChatStreamEvent
          } catch {
            // ignore malformed lines
          }
        }
      }
    }
    // flush remaining buffer
    const trimmed = buffer.trim()
    if (trimmed) {
      try {
        yield JSON.parse(trimmed) as ChatStreamEvent
      } catch {
        // ignore
      }
    }
  } finally {
    reader.releaseLock()
  }
}

// ── Legacy non-streaming API (kept for backward compat) ───────────────────────

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
  mode: ChatMode = 'lookup',
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

export async function askFlat(question: string): Promise<FlatAskResponse> {
  const result = await request<FlatAskResponse>('POST', '/ask/flat', { question })
  if (!result) throw new ApiError(500, 'Không nhận được câu trả lời.')
  return result
}
