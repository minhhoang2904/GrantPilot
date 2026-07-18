import type { SourceItem } from '../types'

function refLabel(item: SourceItem): string {
  const parts: string[] = []
  if (item.article) parts.push(`Điều ${item.article}`)
  if (item.clause) parts.push(`Khoản ${item.clause}`)
  if (item.point) parts.push(`Điểm ${item.point}`)
  return parts.join(', ')
}

interface Props {
  items: SourceItem[]
  onOpenPdf?: (url: string, label: string) => void
}

export default function SourcesPanel({ items, onOpenPdf }: Props) {
  if (!items || items.length === 0) return null

  return (
    <div className="mt-3 space-y-2">
      <p className="text-[11px] uppercase tracking-wide font-semibold text-gray-400">
        Nguồn trích dẫn
      </p>
      <div className="space-y-2">
        {items.map((item) => {
          const ref = refLabel(item)
          const title = [item.document_number, ref].filter(Boolean).join(' · ')

          return (
            <div
              key={item.unit_id}
              className="rounded-lg border border-gray-200 bg-gray-50 px-3 py-2.5 text-xs"
            >
              <div className="flex items-start justify-between gap-2 mb-1">
                <p className="font-medium text-gray-700 leading-snug">{item.document_title}</p>
                {item.source_url ? (
                  <button
                    type="button"
                    onClick={() => onOpenPdf?.(item.source_url!, title || 'Xem tài liệu')}
                    className="shrink-0 flex items-center gap-1 text-brand hover:text-brand-dark underline underline-offset-2 transition whitespace-nowrap"
                  >
                    {title || 'Xem'}
                    <svg className="w-3 h-3 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                  </button>
                ) : (
                  title && <span className="shrink-0 text-gray-500 whitespace-nowrap">{title}</span>
                )}
              </div>
              {item.snippet && (
                <p className="text-gray-500 leading-relaxed line-clamp-3">{item.snippet}</p>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
