import { useRef, useState } from 'react'

interface Props {
  onSend: (question: string) => void
  disabled: boolean
}

export default function ChatInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSubmit(e?: React.FormEvent) {
    e?.preventDefault()
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setValue(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  return (
    <div className="border-t border-gray-200 bg-white px-6 py-4">
      <form onSubmit={handleSubmit} className="flex gap-3 items-end">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Hỏi về ưu đãi / chính sách hỗ trợ doanh nghiệp... (Enter để gửi)"
          className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition disabled:opacity-50 disabled:cursor-not-allowed leading-relaxed"
          style={{ minHeight: '48px', maxHeight: '160px' }}
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="flex-shrink-0 w-11 h-11 bg-brand hover:bg-brand-dark disabled:opacity-40 text-white rounded-xl flex items-center justify-center transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
              d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
          </svg>
        </button>
      </form>
      <p className="mt-2 text-xs text-gray-400 text-center">
        Shift + Enter để xuống dòng
      </p>
    </div>
  )
}
