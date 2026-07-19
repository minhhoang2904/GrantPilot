import { useEffect, useRef } from 'react'
import type { ChatMode, Message } from '../types'
import ResultsTable from './ResultsTable'

function UserBubble({ content }: { content: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[75%] bg-brand text-white px-4 py-3 rounded-2xl rounded-tr-sm text-sm leading-relaxed shadow-sm">
        {content}
      </div>
    </div>
  )
}

function AssistantBubble({ content, results, streaming }: { content: string; results?: Message['results']; streaming?: boolean }) {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-brand to-purple-500 rounded-full flex items-center justify-center shadow-sm">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <div className="flex-1 min-w-0">
        <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-tl-sm text-sm leading-relaxed text-gray-800 shadow-sm whitespace-pre-wrap">
          {content || (streaming ? 'Đang phân tích hồ sơ và chính sách...' : '')}
          {streaming && <span className="inline-block ml-0.5 text-brand animate-pulse">▍</span>}
        </div>
        {results && results.length > 0 && <ResultsTable results={results} />}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div className="flex gap-3 items-start">
      <div className="flex-shrink-0 w-8 h-8 bg-gradient-to-br from-brand to-purple-500 rounded-full flex items-center justify-center shadow-sm">
        <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </div>
      <div className="bg-white border border-gray-200 px-4 py-3 rounded-2xl rounded-tl-sm shadow-sm">
        <div className="flex gap-1 items-center h-5">
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
          <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
        </div>
      </div>
    </div>
  )
}

interface Props {
  messages: Message[]
  loading: boolean
  mode?: ChatMode
  onSend?: (question: string) => void
}

export default function ChatThread({ messages, loading, mode = 'rag', onSend }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  if (messages.length === 0 && !loading) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-center px-6 py-16">
        <div className="w-16 h-16 bg-brand/10 rounded-2xl flex items-center justify-center mb-4">
          <svg className="w-8 h-8 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
        </div>
        <h3 className="text-base font-semibold text-gray-700 mb-1">Bắt đầu tư vấn chính sách</h3>
        <p className="text-sm text-gray-400 max-w-xs">
          {mode === 'eligibility'
            ? 'Hỏi về ưu đãi / chính sách — chế độ Tư vấn sâu đối chiếu với hồ sơ doanh nghiệp để xem bạn đủ điều kiện hay chưa.'
            : 'Hỏi về ưu đãi hay chính sách hỗ trợ. Chế độ Tra cứu nhanh không yêu cầu hồ sơ doanh nghiệp.'}
        </p>
        <div className="mt-6 grid grid-cols-1 gap-2 w-full max-w-sm text-left">
          {[
            'Tôi có đủ điều kiện nhận ưu đãi thuế TNDN không?',
            'Doanh nghiệp tôi có thể xin quỹ NATIF không?',
            'Có chính sách nào hỗ trợ doanh nghiệp công nghệ không?',
          ].map((q) => (
            <button
              key={q}
              type="button"
              disabled={!onSend}
              onClick={() => onSend?.(q)}
              className="w-full px-3 py-2.5 rounded-lg border border-gray-200 text-xs text-gray-600 bg-gray-50 text-left hover:border-brand hover:bg-brand/5 hover:text-brand transition disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto chat-scroll px-6 py-6 space-y-5">
      {messages.map((msg) =>
        msg.role === 'user' ? (
          <UserBubble key={msg.id} content={msg.content} />
        ) : (
          <AssistantBubble key={msg.id} content={msg.content} results={msg.results} streaming={msg.streaming} />
        ),
      )}
      {loading && !messages.some((message) => message.streaming) && <TypingIndicator />}
      <div ref={bottomRef} />
    </div>
  )
}
