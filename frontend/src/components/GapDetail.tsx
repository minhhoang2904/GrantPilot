import { useState } from 'react'
import type { PolicyResult } from '../types'

function formatVND(value: number): string {
  return new Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' }).format(value)
}

interface Props {
  result: PolicyResult
}

export default function GapDetail({ result }: Props) {
  const [open, setOpen] = useState(false)
  const hasGap = result.gap && result.gap.length > 0
  const hasRoi = result.roi_missed && result.roi_missed > 0

  if (!hasGap && !hasRoi) return null

  return (
    <div className="mt-2">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 text-xs text-brand hover:text-brand-dark font-medium transition"
      >
        <svg
          className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-90' : ''}`}
          fill="none" stroke="currentColor" viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        {open ? 'Ẩn chi tiết' : 'Xem chi tiết gap & ROI'}
      </button>

      {open && (
        <div className="mt-2 pl-3 border-l-2 border-gray-200 space-y-2">
          {hasGap && (
            <div>
              <p className="text-xs font-semibold text-gray-600 mb-1">Còn thiếu để đủ điều kiện:</p>
              <ul className="space-y-0.5">
                {result.gap!.map((reason, i) => (
                  <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                    <span className="text-yellow-500 mt-0.5">•</span>
                    <span>{reason}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasRoi && (
            <p className="text-xs text-gray-600">
              <span className="font-semibold text-gray-700">Giá trị đang bỏ lỡ (ROI): </span>
              <span className="text-red-600 font-medium">{formatVND(result.roi_missed!)}</span>
            </p>
          )}
        </div>
      )}
    </div>
  )
}
