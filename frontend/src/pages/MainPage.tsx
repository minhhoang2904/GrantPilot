import { useState } from 'react'
import type { Company, Message } from '../types'
import { ask, ApiError } from '../api'
import { clearEmail } from '../auth'
import ChatThread from '../components/ChatThread'
import ChatInput from '../components/ChatInput'
import BenchmarkPanel from '../components/BenchmarkPanel'

type Tab = 'chat' | 'benchmark'

interface Props {
  email: string
  company: Company
  onLogout: () => void
}

export default function MainPage({ email, company, onLogout }: Props) {
  const [tab, setTab] = useState<Tab>('chat')
  const [messages, setMessages] = useState<Message[]>([])
  const [loading, setLoading] = useState(false)

  function handleLogout() {
    clearEmail()
    onLogout()
  }

  async function handleSend(question: string) {
    const userMsg: Message = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: question,
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)
    try {
      const res = await ask(email, question)
      const assistantMsg: Message = {
        id: `a-${Date.now()}`,
        role: 'assistant',
        content: res.answer,
        results: res.results,
      }
      setMessages((prev) => [...prev, assistantMsg])
    } catch (err) {
      const errMsg: Message = {
        id: `e-${Date.now()}`,
        role: 'assistant',
        content: err instanceof ApiError ? err.message : 'Đã xảy ra lỗi, vui lòng thử lại.',
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="h-screen flex overflow-hidden bg-gray-50">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 bg-sidebar flex flex-col">
        {/* Brand */}
        <div className="px-5 py-5 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 bg-brand rounded-lg flex items-center justify-center flex-shrink-0">
              <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
            </div>
            <span className="text-white font-semibold text-sm">GrandPilot</span>
          </div>
        </div>

        {/* Company info */}
        <div className="px-5 py-4 border-b border-white/10">
          <p className="text-xs text-gray-400 mb-0.5">Doanh nghiệp</p>
          <p className="text-sm font-semibold text-white truncate">{company.ten_doanh_nghiep}</p>
          <p className="text-xs text-gray-400 truncate">{email}</p>
          {company.linh_vuc && (
            <span className="mt-2 inline-block text-xs bg-white/10 text-gray-300 px-2 py-0.5 rounded-full">
              {company.linh_vuc}
            </span>
          )}
        </div>

        {/* Nav tabs */}
        <nav className="px-3 py-4 flex-1 space-y-1">
          <button
            onClick={() => setTab('chat')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              tab === 'chat'
                ? 'bg-white/15 text-white'
                : 'text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            Tư vấn chính sách
          </button>
          <button
            onClick={() => setTab('benchmark')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
              tab === 'benchmark'
                ? 'bg-white/15 text-white'
                : 'text-gray-400 hover:bg-white/10 hover:text-white'
            }`}
          >
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            So sánh benchmark
          </button>
        </nav>

        {/* Company stats */}
        {(company.so_lao_dong != null || company.tuoi != null) && (
          <div className="px-5 py-4 border-t border-white/10">
            <p className="text-xs text-gray-500 mb-2">Thông tin doanh nghiệp</p>
            <div className="space-y-1">
              {company.tuoi != null && (
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Tuổi DN</span>
                  <span className="text-gray-300">{company.tuoi} năm</span>
                </div>
              )}
              {company.so_lao_dong != null && (
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">Lao động</span>
                  <span className="text-gray-300">{company.so_lao_dong.toLocaleString('vi-VN')}</span>
                </div>
              )}
              {company.ty_le_rnd != null && (
                <div className="flex justify-between text-xs">
                  <span className="text-gray-400">R&D</span>
                  <span className="text-gray-300">{(company.ty_le_rnd * 100).toFixed(0)}%</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Logout */}
        <div className="px-3 py-3 border-t border-white/10">
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
        {tab === 'chat' ? (
          <>
            {/* Chat header */}
            <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-4">
              <h2 className="text-base font-semibold text-gray-800">Tư vấn chính sách</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                Hỏi về ưu đãi và chính sách hỗ trợ doanh nghiệp — hệ thống sẽ kiểm tra điều kiện theo hồ sơ của bạn
              </p>
            </div>
            <ChatThread messages={messages} loading={loading} />
            <ChatInput onSend={handleSend} disabled={loading} />
          </>
        ) : (
          <>
            {/* Benchmark header */}
            <div className="flex-shrink-0 border-b border-gray-200 bg-white px-6 py-4">
              <h2 className="text-base font-semibold text-gray-800">So sánh benchmark</h2>
              <p className="text-xs text-gray-500 mt-0.5">
                So sánh câu trả lời có Eligibility Engine với RAG phẳng thông thường
              </p>
            </div>
            <div className="flex-1 overflow-y-auto chat-scroll">
              <BenchmarkPanel email={email} />
            </div>
          </>
        )}
      </main>
    </div>
  )
}
