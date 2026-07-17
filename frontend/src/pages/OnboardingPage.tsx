import { useState } from 'react'
import { createCompany, ApiError } from '../api'
import type { Company } from '../types'

interface Props {
  email: string
  onComplete: (company: Company) => void
}

export default function OnboardingPage({ email, onComplete }: Props) {
  const [tenDoanh, setTenDoanh] = useState('')
  const [linhVuc, setLinhVuc] = useState('')
  const [tuoi, setTuoi] = useState(1)
  const [soLaoDong, setSoLaoDong] = useState(0)
  const [tyLeRnd, setTyLeRnd] = useState(0)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!tenDoanh.trim()) { setError('Vui lòng nhập tên doanh nghiệp.'); return }
    setError('')
    setSubmitting(true)
    try {
      const company = await createCompany({
        email,
        ten_doanh_nghiep: tenDoanh.trim(),
        linh_vuc: linhVuc.trim() || undefined,
        tuoi,
        so_lao_dong: soLaoDong,
        ty_le_rnd: tyLeRnd / 100,
      })
      onComplete(company)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Đã xảy ra lỗi, vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand rounded-2xl mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Thiết lập hồ sơ doanh nghiệp</h1>
          <p className="mt-2 text-sm text-gray-500">
            Chào mừng <span className="font-medium text-gray-700">{email}</span>. Điền thông tin
            một lần duy nhất — các lần sau sẽ tự động dùng lại khi chat.
          </p>
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Tên doanh nghiệp <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                autoFocus
                value={tenDoanh}
                onChange={(e) => setTenDoanh(e.target.value)}
                placeholder="Công ty TNHH ABC"
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Lĩnh vực / ngành nghề
              </label>
              <input
                type="text"
                value={linhVuc}
                onChange={(e) => setLinhVuc(e.target.value)}
                placeholder="vd: công nghệ, sản xuất, nông nghiệp..."
                className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Tuổi doanh nghiệp (năm)
                </label>
                <input
                  type="number"
                  min={0}
                  value={tuoi}
                  onChange={(e) => setTuoi(Number(e.target.value))}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Số lao động
                </label>
                <input
                  type="number"
                  min={0}
                  value={soLaoDong}
                  onChange={(e) => setSoLaoDong(Number(e.target.value))}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Tỷ lệ chi cho R&D / tổng chi phí:{' '}
                <span className="font-semibold text-brand">{tyLeRnd}%</span>
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={tyLeRnd}
                onChange={(e) => setTyLeRnd(Number(e.target.value))}
                className="w-full accent-brand"
              />
              <div className="flex justify-between text-xs text-gray-400 mt-1">
                <span>0%</span><span>50%</span><span>100%</span>
              </div>
            </div>

            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-60 text-white text-sm font-medium rounded-lg transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
            >
              {submitting ? 'Đang lưu...' : 'Lưu & bắt đầu tư vấn'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
