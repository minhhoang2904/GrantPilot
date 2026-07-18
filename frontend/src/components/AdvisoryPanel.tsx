import { useState } from 'react'
import type { AdvisoryPolicy, AdvisoryResult, EligibilityStatus } from '../types'

const STATUS_CONFIG: Record<EligibilityStatus, { label: string; className: string }> = {
  eligible: {
    label: 'Đủ điều kiện',
    className: 'bg-green-100 text-green-800',
  },
  not_eligible: {
    label: 'Không đủ điều kiện',
    className: 'bg-red-100 text-red-700',
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

function StatusBadge({ status }: { status: EligibilityStatus }) {
  const cfg = STATUS_CONFIG[status] ?? { label: status, className: 'bg-gray-100 text-gray-600' }
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${cfg.className}`}
    >
      {cfg.label}
    </span>
  )
}

function ScoreBar({ score }: { score: number }) {
  const pct = Math.round(score * 100)
  return (
    <div className="flex items-center gap-1.5 mt-1">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-brand rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-[10px] text-gray-400 w-7 text-right">{pct}%</span>
    </div>
  )
}

function PolicyRow({ policy }: { policy: AdvisoryPolicy }) {
  const [open, setOpen] = useState(false)
  const hasMissing = policy.missing_fields.length > 0
  const hasReasons = policy.reasons.length > 0

  return (
    <div className="border-b border-gray-100 last:border-0 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-gray-800 leading-snug">{policy.title}</p>
          <ScoreBar score={policy.score} />
        </div>
        <StatusBadge status={policy.status} />
      </div>

      {(hasMissing || hasReasons) && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className="mt-1.5 flex items-center gap-1 text-[11px] text-brand hover:text-brand-dark font-medium transition"
        >
          <svg
            className={`w-3 h-3 transition-transform ${open ? 'rotate-90' : ''}`}
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
          {open ? 'Ẩn chi tiết' : 'Xem điều kiện thiếu'}
        </button>
      )}

      {open && (
        <div className="mt-2 pl-3 border-l-2 border-gray-200 space-y-2">
          {hasMissing && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 mb-1">Thông tin còn thiếu:</p>
              <ul className="space-y-0.5">
                {policy.missing_fields.map((f) => (
                  <li key={f} className="text-xs text-gray-600 flex gap-1.5">
                    <span className="text-yellow-500 mt-0.5">•</span>
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasReasons && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 mb-1">Lý do:</p>
              <ul className="space-y-0.5">
                {policy.reasons.map((r, i) => (
                  <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                    <span className="text-gray-400 mt-0.5">–</span>
                    <span>{r}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

interface Props {
  result: AdvisoryResult
}

export default function AdvisoryPanel({ result }: Props) {
  if (!result.policies || result.policies.length === 0) return null

  return (
    <div className="mt-3 rounded-xl border border-gray-200 overflow-hidden bg-white">
      <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200">
        <p className="text-[11px] uppercase tracking-wide font-semibold text-gray-400">
          Đánh giá hồ sơ doanh nghiệp
        </p>
      </div>
      {result.explanation && (
        <div className="px-4 py-3 border-b border-gray-100 text-xs text-gray-600 leading-relaxed bg-teal-50/50">
          {result.explanation}
        </div>
      )}
      <div className="divide-y divide-gray-100">
        {result.policies.map((p) => (
          <PolicyRow key={p.policy_id} policy={p} />
        ))}
      </div>
    </div>
  )
}
