import { useState } from 'react'
import { apiRegister, apiLogin, ApiError } from '../api'
import { setSession } from '../auth'

interface Props {
  onLogin: (email: string) => void
}

type Tab = 'login' | 'register'

const inputCls =
  'w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition'

export default function LoginPage({ onLogin }: Props) {
  const [tab, setTab] = useState<Tab>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  function switchTab(t: Tab) {
    setTab(t)
    setError('')
    setPassword('')
    setConfirmPassword('')
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')

    const trimEmail = email.trim().toLowerCase()
    if (!trimEmail || !trimEmail.includes('@')) {
      setError('Địa chỉ email không hợp lệ.')
      return
    }
    if (password.length < 6) {
      setError('Mật khẩu tối thiểu 6 ký tự.')
      return
    }
    if (tab === 'register' && password !== confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.')
      return
    }

    setSubmitting(true)
    try {
      const fn = tab === 'register' ? apiRegister : apiLogin
      const { token, email: returnedEmail } = await fn(trimEmail, password)
      setSession(token, returnedEmail)
      onLogin(returnedEmail)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        if (tab === 'register' && err.status === 409) setTab('login')
      } else {
        setError('Đã xảy ra lỗi, vui lòng thử lại.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="w-full max-w-sm">

        {/* Brand */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand rounded-2xl mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">GrandPilot</h1>
          <p className="mt-1 text-sm text-gray-500">Tư vấn ưu đãi và chính sách doanh nghiệp</p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 overflow-hidden">

          {/* Tabs */}
          <div className="flex border-b border-gray-200">
            {(['login', 'register'] as Tab[]).map((t) => (
              <button
                key={t}
                onClick={() => switchTab(t)}
                className={`flex-1 py-3 text-sm font-medium transition ${
                  tab === t
                    ? 'text-brand border-b-2 border-brand bg-white'
                    : 'text-gray-500 hover:text-gray-700 bg-gray-50'
                }`}
              >
                {t === 'login' ? 'Đăng nhập' : 'Đăng ký tài khoản'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="p-8 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Email công ty</label>
              <input
                type="email"
                autoFocus
                required
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError('') }}
                placeholder="ten@congty.vn"
                className={inputCls}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mật khẩu</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError('') }}
                placeholder="Tối thiểu 6 ký tự"
                className={inputCls}
              />
            </div>

            {tab === 'register' && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Xác nhận mật khẩu</label>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => { setConfirmPassword(e.target.value); setError('') }}
                  placeholder="Nhập lại mật khẩu"
                  className={inputCls}
                />
              </div>
            )}

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-2.5 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-60 text-white text-sm font-medium rounded-lg transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
            >
              {submitting
                ? 'Đang xử lý...'
                : tab === 'login' ? 'Đăng nhập' : 'Tạo tài khoản →'}
            </button>

            <p className="text-center text-xs text-gray-400">
              {tab === 'login'
                ? <>Chưa có tài khoản?{' '}
                    <button type="button" onClick={() => switchTab('register')}
                      className="text-brand hover:underline font-medium">Đăng ký ngay</button></>
                : <>Đã có tài khoản?{' '}
                    <button type="button" onClick={() => switchTab('login')}
                      className="text-brand hover:underline font-medium">Đăng nhập</button></>
              }
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
