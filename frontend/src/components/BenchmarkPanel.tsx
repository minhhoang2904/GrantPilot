import { useState } from 'react'
import { ask, askFlat, ApiError } from '../api'
import type { AskResponse, FlatAskResponse } from '../types'
import ResultsTable from './ResultsTable'

interface Props {
  email: string
}

export default function BenchmarkPanel({ email }: Props) {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [full, setFull] = useState<AskResponse | null>(null)
  const [flat, setFlat] = useState<FlatAskResponse | null>(null)
  const [fullError, setFullError] = useState('')
  const [flatError, setFlatError] = useState('')
  const [hasRun, setHasRun] = useState(false)

  async function handleCompare(e: React.FormEvent) {
    e.preventDefault()
    if (!question.trim() || loading) return
    setLoading(true)
    setFull(null)
    setFlat(null)
    setFullError('')
    setFlatError('')
    setHasRun(true)

    await Promise.all([
      ask(email, question.trim())
        .then(setFull)
        .catch((err: unknown) => {
          setFullError(err instanceof ApiError ? err.message : 'Lỗi không xác định.')
        }),
      askFlat(question.trim())
        .then(setFlat)
        .catch((err: unknown) => {
          setFlatError(err instanceof ApiError ? err.message : 'Lỗi không xác định.')
        }),
    ])
    setLoading(false)
  }

  return (
    <div className="p-6 space-y-6">
      {/* Input */}
      <form onSubmit={handleCompare} className="flex gap-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Nhập câu hỏi để so sánh hai pipeline..."
          className="flex-1 px-4 py-2.5 rounded-xl border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition"
        />
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="px-5 py-2.5 bg-brand hover:bg-brand-dark disabled:opacity-50 text-white text-sm font-medium rounded-xl transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2 whitespace-nowrap"
        >
          {loading ? 'Đang so sánh...' : 'So sánh'}
        </button>
      </form>

      {!hasRun && (
        <div className="text-center py-16 text-gray-400">
          <svg className="w-12 h-12 mx-auto mb-3 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
          </svg>
          <p className="text-sm">Nhập câu hỏi và nhấn "So sánh" để xem kết quả</p>
        </div>
      )}

      {hasRun && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Eligibility-aware */}
          <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
            <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              <h3 className="text-sm font-semibold text-gray-800">Có Eligibility Engine</h3>
            </div>
            <div className="p-5">
              {loading ? (
                <div className="space-y-2 animate-pulse">
                  <div className="h-3 bg-gray-200 rounded w-full" />
                  <div className="h-3 bg-gray-200 rounded w-5/6" />
                  <div className="h-3 bg-gray-200 rounded w-4/6" />
                </div>
              ) : fullError ? (
                <p className="text-sm text-red-600">{fullError}</p>
              ) : full ? (
                <>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{full.answer}</p>
                  <ResultsTable results={full.results} />
                </>
              ) : null}
            </div>
          </div>

          {/* Flat RAG */}
          <div className="rounded-2xl border border-gray-200 bg-white overflow-hidden">
            <div className="px-5 py-3.5 border-b border-gray-100 flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-gray-400" />
              <h3 className="text-sm font-semibold text-gray-800">RAG phẳng (baseline)</h3>
            </div>
            <div className="p-5">
              {loading ? (
                <div className="space-y-2 animate-pulse">
                  <div className="h-3 bg-gray-200 rounded w-full" />
                  <div className="h-3 bg-gray-200 rounded w-5/6" />
                  <div className="h-3 bg-gray-200 rounded w-4/6" />
                </div>
              ) : flatError ? (
                <p className="text-sm text-red-600">{flatError}</p>
              ) : flat ? (
                <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">{flat.answer}</p>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
