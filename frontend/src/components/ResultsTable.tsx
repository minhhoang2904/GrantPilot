import type { PolicyResult, PolicyStatus } from '../types'
import GapDetail from './GapDetail'

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
}

function StatusBadge({ status }: { status: PolicyStatus }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, className: 'bg-gray-100 text-gray-600' }
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${cfg.className}`}>
      {cfg.label}
    </span>
  )
}

function SourceLink({ source }: { source: PolicyResult['source'] }) {
  if (!source) return <span className="text-gray-400">—</span>
  const parts = [source.dieu, source.khoan, source.thong_tu].filter(Boolean).join(', ')
  const label = parts || 'Nguồn'
  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-brand hover:text-brand-dark text-xs underline underline-offset-2"
      >
        {label}
      </a>
    )
  }
  return <span className="text-xs text-gray-600">{label}</span>
}

interface Props {
  results: PolicyResult[]
}

export default function ResultsTable({ results }: Props) {
  if (!results || results.length === 0) return null

  return (
    <div className="mt-3 rounded-xl border border-gray-200 overflow-hidden bg-white">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="w-[55%] px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Chính sách</th>
              <th className="w-[20%] px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Trạng thái</th>
              <th className="w-[25%] px-4 py-2.5 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide">Nguồn</th>
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
                <td className="px-4 py-3 align-top">
                  <SourceLink source={r.source} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
