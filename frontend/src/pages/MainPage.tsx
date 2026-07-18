import { useState, useEffect } from 'react'
import type { ChatMode, Company, LegalForm, Message, Sector } from '../types'
import { chatStream, deleteSession, getHistory, ApiError, type HistorySession } from '../api'
import { clearSession } from '../auth'
import ChatThread from '../components/ChatThread'
import ChatInput from '../components/ChatInput'
import PdfSidePanel from '../components/PdfSidePanel'

// ── helpers ───────────────────────────────────────────────────────────────────

const MODE_KEY = 'gp_chat_mode'

const SECTOR_LABELS: Record<Sector, string> = {
  nong_lam_ngu_nghiep: 'Nông / Lâm / Ngư',
  cong_nghiep_xay_dung: 'CN & Xây dựng',
  thuong_mai_dich_vu: 'TM & Dịch vụ',
}

const LEGAL_FORM_LABELS: Record<LegalForm, string> = {
  joint_stock_company: 'Công ty cổ phần',
  limited_liability_company: 'Công ty TNHH',
  partnership: 'Công ty hợp danh',
  private_enterprise: 'Doanh nghiệp tư nhân',
  cooperative: 'Hợp tác xã',
  household_business: 'Hộ kinh doanh',
  other: 'Khác',
}

function sectorLabel(s?: Sector | null) {
  return s ? SECTOR_LABELS[s] : null
}

function triboolLabel(v?: boolean | null) {
  if (v === true) return 'Có'
  if (v === false) return 'Không'
  return null
}

function compactVnd(n?: number | null) {
  if (n == null) return null
  return (
    new Intl.NumberFormat('vi-VN', { notation: 'compact', maximumFractionDigits: 1 }).format(n) +
    ' ₫'
  )
}

/** Profile is complete when all eligibility-required fields are filled. */
export function isProfileComplete(company: Company | null | undefined): boolean {
  if (!company?.company_name?.trim()) return false
  if (company.profile_schema_version !== 'company-profile-v1') return false
  if (!company.sector) return false
  if (!company.primary_business_activity_group) return false
  if (!company.legal_form) return false
  if (company.social_insurance_employees == null) return false
  if (company.annual_revenue_vnd == null) return false
  if (company.total_capital_vnd == null) return false
  if (!company.first_business_registration_date) return false
  if (!company.business_description?.trim()) return false
  if (company.has_public_offering == null) return false
  if (!company.province_name?.trim()) return false
  if (company.has_coworking_contract == null) return false
  if (company.has_business_registration == null) return false
  if (company.has_coworking_contract && company.coworking_monthly_cost_vnd == null) return false
  return true
}

function loadStoredMode(): ChatMode {
  try {
    const v = localStorage.getItem(MODE_KEY)
    if (v === 'lookup' || v === 'advisory') return v
    // Migrate old values
    if (v === 'eligibility') return 'advisory'
    if (v === 'rag') return 'lookup'
  } catch {
    /* ignore */
  }
  return 'lookup'
}

function sessionTitle(session: HistorySession, index: number): string {
  const firstUser = session.turns.find((t) => t.role === 'user')
  if (firstUser?.content?.trim()) {
    const t = firstUser.content.trim()
    return t.length > 42 ? t.slice(0, 42) + '…' : t
  }
  return `Cuộc trò chuyện ${index + 1}`
}

function turnsToMessages(turns: HistorySession['turns']): Message[] {
  return turns.map((t, i) => ({
    id: `h-${i}`,
    role: t.role,
    content: t.content,
    results: t.results as Message['results'],
  }))
}

function sessionMode(session: HistorySession): ChatMode | null {
  for (let i = session.turns.length - 1; i >= 0; i -= 1) {
    const turnMode = session.turns[i].mode
    if (turnMode === 'lookup' || turnMode === 'advisory') return turnMode
  }
  return null
}

function SidebarStat({ label, value }: { label: string; value: string | null }) {
  return (
    <div className="flex justify-between gap-2 text-xs">
      <span className="text-gray-400 shrink-0">{label}</span>
      <span className={`text-right truncate ${value ? 'text-gray-200' : 'text-gray-600 italic'}`}>
        {value ?? 'null'}
      </span>
    </div>
  )
}

interface Props {
  email: string
  company: Company | null
  onLogout: () => void
  onOpenOnboarding: (required: boolean) => void
}

export default function MainPage({
  email,
  company,
  onLogout,
  onOpenOnboarding,
}: Props) {
  const [mode, setMode] = useState<ChatMode>(loadStoredMode)
  const [sessions, setSessions] = useState<HistorySession[]>([])
  const [messages, setMessages] = useState<Message[]>([])
  const [sessionId, setSessionId] = useState<string | undefined>(undefined)
  const [loading, setLoading] = useState(false)
  const [historyLoading, setHistoryLoading] = useState(true)
  const [pdfUrl, setPdfUrl] = useState<string | null>(null)
  const [pdfLabel, setPdfLabel] = useState<string>('')

  function handleOpenPdf(url: string, label: string) {
    setPdfUrl(url)
    setPdfLabel(label)
  }

  const profileComplete = isProfileComplete(company)

  function persistMode(next: ChatMode) {
    setMode(next)
    try {
      localStorage.setItem(MODE_KEY, next)
    } catch {
      /* ignore */
    }
  }

  function restoreSessionMode(session: HistorySession) {
    const storedMode = sessionMode(session)
    if (storedMode) persistMode(storedMode)
  }

  // Advisory mode needs a complete profile — fall back to lookup otherwise
  useEffect(() => {
    if (mode === 'advisory' && !profileComplete) {
      persistMode('lookup')
    }
  }, [mode, profileComplete])

  useEffect(() => {
    async function loadHistory() {
      setHistoryLoading(true)
      try {
        const list = await getHistory(email)
        // Newest last from API — show newest first in sidebar
        setSessions(list)
        if (list.length > 0) {
          const latest = list[list.length - 1]
          setSessionId(latest.session_id)
          setMessages(turnsToMessages(latest.turns))
          restoreSessionMode(latest)
        } else {
          setSessionId(undefined)
          setMessages([])
        }
      } catch {
        setSessions([])
        setSessionId(undefined)
        setMessages([])
      } finally {
        setHistoryLoading(false)
      }
    }
    void loadHistory()
  }, [email])

  function handleModeChange(next: ChatMode) {
    if (next === 'advisory' && !profileComplete) {
      onOpenOnboarding(true)
      return
    }
    persistMode(next)
  }

  function handleLogout() {
    clearSession()
    onLogout()
  }

  function selectSession(session: HistorySession) {
    setSessionId(session.session_id)
    setMessages(turnsToMessages(session.turns))
    restoreSessionMode(session)
  }

  function handleNewChat() {
    setSessionId(undefined)
    setMessages([])
  }

  async function handleDeleteSession(e: React.MouseEvent, sid: string) {
    e.stopPropagation()
    try {
      await deleteSession(email, sid)
      const next = sessions.filter((s) => s.session_id !== sid)
      setSessions(next)
      if (sessionId === sid) {
        if (next.length > 0) {
          const latest = next[next.length - 1]
          setSessionId(latest.session_id)
          setMessages(turnsToMessages(latest.turns))
          restoreSessionMode(latest)
        } else {
          setSessionId(undefined)
          setMessages([])
        }
      }
    } catch {
      /* ignore */
    }
  }

  async function handleSend(question: string) {
    if (mode === 'advisory' && !profileComplete) {
      onOpenOnboarding(true)
      return
    }

    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: question,
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    const assistantId = `a-${Date.now()}`
    let assistantStarted = false

    try {
      for await (const event of chatStream(question, mode, sessionId ?? null)) {
        switch (event.type) {
          case 'started':
            setSessionId(event.conversation_id)
            break

          case 'answer_delta':
            if (!assistantStarted) {
              assistantStarted = true
              setMessages((prev) => [
                ...prev,
                { id: assistantId, role: 'assistant', content: event.text },
              ])
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: m.content + event.text } : m,
                ),
              )
            }
            break

          case 'sources':
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, sources: event.items } : m,
              ),
            )
            break

          case 'advisory_result':
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, advisoryResult: event.data } : m,
              ),
            )
            break

          case 'warning':
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, warning: event.message } : m,
              ),
            )
            break

          case 'error':
            if (!assistantStarted) {
              assistantStarted = true
              setMessages((prev) => [
                ...prev,
                { id: assistantId, role: 'assistant', content: event.error.message },
              ])
            } else {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: m.content
                          ? `${m.content}\n\n⚠️ ${event.error.message}`
                          : event.error.message,
                      }
                    : m,
                ),
              )
            }
            break

          case 'completed':
            void getHistory(email).then(setSessions)
            break
        }
      }
    } catch (err) {
      const errText =
        err instanceof ApiError ? err.message : 'Đã xảy ra lỗi, vui lòng thử lại.'
      if (!assistantStarted) {
        setMessages((prev) => [
          ...prev,
          { id: assistantId, role: 'assistant', content: errText },
        ])
      } else {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: m.content ? `${m.content}\n\n⚠️ ${errText}` : errText,
                }
              : m,
          ),
        )
      }
    } finally {
      setLoading(false)
    }
  }

  const sessionsNewestFirst = [...sessions].reverse()

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-72 flex-shrink-0 bg-sidebar flex flex-col">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-brand rounded-lg flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="text-white font-semibold text-sm">GrantPilot</span>
          </div>
        </div>

        {/* Mode toggle */}
        <div className="px-4 py-3 border-b border-white/10">
          <p className="text-[11px] uppercase tracking-wide text-gray-500 mb-2">Chế độ tư vấn</p>
          <div className="grid grid-cols-2 gap-1 p-1 rounded-lg bg-white/5">
            <button
              type="button"
              onClick={() => handleModeChange('lookup')}
              className={`px-2 py-2 rounded-md text-xs font-medium transition leading-tight ${
                mode === 'lookup'
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-white/10'
              }`}
            >
              Tra cứu nhanh
            </button>
            <button
              type="button"
              onClick={() => handleModeChange('advisory')}
              className={`px-2 py-2 rounded-md text-xs font-medium transition leading-tight ${
                mode === 'advisory'
                  ? 'bg-brand text-white shadow-sm'
                  : 'text-gray-400 hover:text-white hover:bg-white/10'
              }`}
            >
              Tư vấn sâu
            </button>
          </div>
          {mode === 'advisory' && !profileComplete && (
            <p className="mt-2 text-[11px] text-amber-400/90 leading-snug">
              Cần hồ sơ doanh nghiệp đầy đủ để dùng chế độ này.
            </p>
          )}
        </div>

        {/* Sessions */}
        <div className="flex-1 min-h-0 flex flex-col border-b border-white/10">
          <div className="px-4 pt-3 pb-2 flex items-center justify-between gap-2">
            <p className="text-[11px] uppercase tracking-wide text-gray-500">Cuộc trò chuyện</p>
            <button
              type="button"
              onClick={handleNewChat}
              className="text-[11px] font-medium text-brand hover:text-white transition"
            >
              + Mới
            </button>
          </div>
          <div className="flex-1 overflow-y-auto chat-scroll px-2 pb-2 space-y-0.5">
            {historyLoading ? (
              <p className="px-2 py-3 text-xs text-gray-500">Đang tải...</p>
            ) : sessionsNewestFirst.length === 0 ? (
              <p className="px-2 py-3 text-xs text-gray-500 italic">Chưa có phiên chat</p>
            ) : (
              sessionsNewestFirst.map((s, i) => {
                const active = s.session_id === sessionId
                const idx = sessions.length - 1 - i
                return (
                  <div
                    key={s.session_id}
                    className={`group w-full text-left px-2.5 py-2 rounded-lg transition flex items-start gap-2 ${
                      active
                        ? 'bg-white/15 text-white'
                        : 'text-gray-400 hover:bg-white/10 hover:text-white'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => selectSession(s)}
                      className="flex-1 min-w-0 flex items-start gap-2 text-left"
                    >
                      <svg className="w-3.5 h-3.5 mt-0.5 shrink-0 opacity-70" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                      </svg>
                      <span className="flex-1 min-w-0">
                        <span className="block text-xs font-medium truncate">
                          {sessionTitle(s, idx)}
                        </span>
                        <span className="block text-[10px] text-gray-500 mt-0.5">
                          {s.started_at
                            ? new Date(s.started_at).toLocaleDateString('vi-VN')
                            : '—'}
                          {' · '}
                          {s.turns.length} tin
                        </span>
                      </span>
                    </button>
                    <button
                      type="button"
                      onClick={(e) => void handleDeleteSession(e, s.session_id)}
                      className="opacity-0 group-hover:opacity-100 p-0.5 rounded text-gray-500 hover:text-red-400 transition shrink-0"
                      title="Xóa phiên"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                          d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                )
              })
            )}
            {/* Draft new chat indicator */}
            {!historyLoading && sessionId === undefined && (
              <div className="px-2.5 py-2 rounded-lg bg-white/10 text-white text-xs font-medium">
                Cuộc trò chuyện mới
              </div>
            )}
          </div>
        </div>

        {/* Profile */}
        <div className="px-4 py-3 border-b border-white/10 max-h-56 overflow-y-auto chat-scroll">
          <div className="flex items-center justify-between mb-2">
            <p className="text-[11px] uppercase tracking-wide text-gray-500">Hồ sơ cá nhân</p>
            <button
              type="button"
              onClick={() => onOpenOnboarding(false)}
              className="text-[11px] font-medium text-brand hover:text-white transition"
            >
              {profileComplete ? 'Sửa' : 'Điền hồ sơ'}
            </button>
          </div>
          <p className="text-sm font-semibold text-white truncate mb-0.5">
            {company?.company_name?.trim() || 'Chưa có tên DN'}
          </p>
          <p className="text-xs text-gray-400 truncate mb-2">{email}</p>
          <div className="space-y-1">
            <SidebarStat label="Lĩnh vực" value={sectorLabel(company?.sector)} />
            <SidebarStat label="Loại hình" value={company?.legal_form ? LEGAL_FORM_LABELS[company.legal_form] : null} />
            <SidebarStat label="Đăng ký lần đầu" value={company?.first_business_registration_date ?? null} />
            <SidebarStat
              label="LĐ BHXH"
              value={
                company?.social_insurance_employees != null
                  ? String(company.social_insurance_employees)
                  : null
              }
            />
            <SidebarStat label="Doanh thu" value={compactVnd(company?.annual_revenue_vnd)} />
            <SidebarStat label="Tổng vốn" value={compactVnd(company?.total_capital_vnd)} />
            <SidebarStat label="SP / DV" value={company?.business_description ?? null} />
            <SidebarStat label="Tỉnh / TP" value={company?.province_name ?? null} />
            <SidebarStat
              label="Chào bán CK"
              value={triboolLabel(company?.has_public_offering)}
            />
            <SidebarStat label="ĐKKD" value={triboolLabel(company?.has_business_registration)} />
            <SidebarStat
              label="Coworking"
              value={triboolLabel(company?.has_coworking_contract)}
            />
            <SidebarStat
              label="Chi phí CW"
              value={compactVnd(company?.coworking_monthly_cost_vnd)}
            />
          </div>
        </div>

        {/* Logout */}
        <div className="px-3 py-3">
          <button
            onClick={handleLogout}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-sm text-gray-400 hover:bg-white/10 hover:text-white transition"
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
            </svg>
            Đăng xuất
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        <div
          className={`flex-shrink-0 border-b px-6 py-4 transition-colors ${
            mode === 'advisory'
              ? 'bg-teal-50 border-teal-200'
              : 'bg-sky-50 border-sky-200'
          }`}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="flex items-center gap-2.5">
                <span
                  className={`w-1 h-5 rounded-full shrink-0 ${
                    mode === 'advisory' ? 'bg-teal-600' : 'bg-sky-600'
                  }`}
                />
                <h2
                  className={`text-base font-semibold ${
                    mode === 'advisory' ? 'text-teal-900' : 'text-sky-900'
                  }`}
                >
                  {mode === 'advisory' ? 'Tư vấn sâu theo hồ sơ' : 'Tra cứu chính sách nhanh'}
                </h2>
              </div>
              <p
                className={`text-xs mt-1.5 pl-[14px] ${
                  mode === 'advisory' ? 'text-teal-700/80' : 'text-sky-700/80'
                }`}
              >
                {mode === 'advisory'
                  ? 'Đối chiếu ưu đãi với hồ sơ doanh nghiệp của bạn — biết ngay đủ điều kiện hay còn thiếu gì.'
                  : 'Hỏi đáp chính sách hỗ trợ nhanh, không cần điền hồ sơ doanh nghiệp.'}
              </p>
            </div>
            <span
              className={`shrink-0 text-[11px] font-semibold px-2.5 py-1 rounded-md ${
                mode === 'advisory'
                  ? 'bg-teal-600 text-white'
                  : 'bg-sky-600 text-white'
              }`}
            >
              {mode === 'advisory' ? 'Tư vấn sâu' : 'Tra cứu nhanh'}
            </span>
          </div>
        </div>
        {historyLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="flex flex-col items-center gap-2">
              <div className="w-6 h-6 border-2 border-brand border-t-transparent rounded-full animate-spin" />
              <p className="text-xs text-gray-400">Đang tải lịch sử...</p>
            </div>
          </div>
        ) : (
          <ChatThread
            messages={messages}
            loading={loading}
            mode={mode}
            onSend={loading || historyLoading ? undefined : handleSend}
            onOpenPdf={handleOpenPdf}
          />
        )}
        <ChatInput onSend={handleSend} disabled={loading || historyLoading} />
      </main>

      {/* PDF side panel */}
      {pdfUrl && (
        <PdfSidePanel
          url={pdfUrl}
          label={pdfLabel}
          onClose={() => setPdfUrl(null)}
        />
      )}
    </div>
  )
}
