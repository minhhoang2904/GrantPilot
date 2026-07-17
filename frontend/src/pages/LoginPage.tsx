import { useState } from 'react'
import { setEmail } from '../auth'

interface Props {
  onLogin: (email: string) => void
}

export default function LoginPage({ onLogin }: Props) {
  const [value, setValue] = useState('')
  const [error, setError] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) {
      setError('Vui lòng nhập email.')
      return
    }
    if (!trimmed.includes('@')) {
      setError('Địa chỉ email không hợp lệ.')
      return
    }
    setEmail(trimmed)
    onLogin(trimmed)
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo / brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand rounded-2xl mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">GrandPilot</h1>
          <p className="mt-1 text-sm text-gray-500">
            Tư vấn ưu đãi và chính sách doanh nghiệp
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">Đăng nhập</h2>
          <p className="text-sm text-gray-500 mb-6">
            Nhập email công ty để bắt đầu tư vấn chính sách.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
                Email công ty
              </label>
              <input
                id="email"
                type="email"
                autoFocus
                value={value}
                onChange={(e) => { setValue(e.target.value); setError('') }}
                placeholder="ten@congty.vn"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition"
              />
              {error && <p className="mt-1.5 text-xs text-red-600">{error}</p>}
            </div>
            <button
              type="submit"
              className="w-full py-2.5 px-4 bg-brand hover:bg-brand-dark text-white text-sm font-medium rounded-lg transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
            >
              Đăng nhập
            </button>
          </form>

          <p className="mt-4 text-xs text-center text-gray-400">
            Chế độ dev — nhập email bất kỳ để thử nghiệm
          </p>
        </div>
      </div>
    </div>
  )
}
