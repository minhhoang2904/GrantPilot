import type { PolicyResult, PolicyStatus } from '../types'
import GapDetail from './GapDetail'

function formatVND(value?: number): string {
  if (value == null || value === 0) return '—'
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value)
}

const STATUS_CONFIG: Record<PolicyStatus, { label: string; className: string }> = {
  eligible: {
    label: 'Đủ điều kiện',
    className: 'bg-green-100 text-green-800',
  },
  partial: {
    label: 'Thiếu — khắc phục được',
    className: 'bg-yellow-100 text-yellow-800',
  },
  not_eligible: {
    label: 'Không đủ điều kiện',
    className: 'bg-red-100 text-red-700',
  },
  expired: {
    label: 'Đã hết hạn',
    className: 'bg-gray-100 text-gray-600',
  },
  needs_more_information: {
    label: 'Cần thêm thông tin',
    className: 'bg-yellow-100 text-yellow-800',
  },
  manual_review: {
    label: 'Cần xem xét thêm',
    className: 'bg-blue-100 text-blue-700',
  },
}

function StatusBadge({ status }: { status: PolicyStatus }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, className: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

function SourceLink({
  source,
  onOpenPdf,
}: {
  source: PolicyResult['source']
  onOpenPdf?: (url: string, label: string) => void
}) {
  if (!source) return <span className="text-gray-400">—</span>
  const parts = [source.dieu, source.khoan, source.thong_tu].filter(Boolean).join(', ')
  const label = parts || 'Nguồn'
  if (source.url) {
    return (
      <button
        type="button"
        onClick={() => onOpenPdf?.(source.url!, label)}
        className="flex items-center gap-1 text-brand hover:text-brand-dark text-xs underline underline-offset-2 text-left transition"
      >
        {label}
        <svg className="w-3 h-3 opacity-60 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
            d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      </button>
    )
  }
  return <span className="text-xs text-gray-600">{label}</span>
}

interface Props {
  results: PolicyResult[]
  onOpenPdf?: (url: string, label: string) => void
}

export default function ResultsTable({ results, onOpenPdf }: Props) {
  if (!results || results.length === 0) return null

  return (
    <div className="mt-3 rounded-xl border border-gray-200 overflow-hidden bg-white">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Chính sách</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Trạng thái</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Giá trị</th>
              <th className="px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Nguồn</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {results.map((r) => (
              <tr key={r.policy_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-800 text-xs leading-tight">{r.title}</p>
                  <GapDetail result={r} />
                </td>
                <td className="px-4 py-3 align-top">
                  <StatusBadge status={r.status} />
                </td>
                <td className="px-4 py-3 align-top text-xs text-gray-700 whitespace-nowrap">
                  {formatVND(r.value)}
                </td>
                <td className="px-4 py-3 align-top">
                  <SourceLink source={r.source} onOpenPdf={onOpenPdf} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
