import { useState } from 'react'

interface Props {
  url: string
  label: string
  onClose: () => void
}

function isPdfUrl(url: string): boolean {
  try {
    const path = new URL(url).pathname.toLowerCase()
    return path.endsWith('.pdf')
  } catch {
    return false
  }
}

export default function PdfSidePanel({ url, label, onClose }: Props) {
  const [iframeError, setIframeError] = useState(false)
  const isInsecureHttp = url.trim().toLowerCase().startsWith('http://')
  const isPdf = isPdfUrl(url)

  // PDFs from chinhphu.vn allow direct iframe embedding and render natively
  // in the browser. Non-PDF URLs (HTML law pages) often block iframe via
  // X-Frame-Options, so we show an "open in new tab" prompt instead.
  const canEmbed = !isInsecureHttp && isPdf && !iframeError

  return (
    <div className="flex flex-col w-[480px] flex-shrink-0 border-l border-gray-200 bg-white">
      {/* Header */}
      <div className="flex-shrink-0 flex items-center justify-between gap-2 px-4 py-3 border-b border-gray-200 bg-gray-50">
        <span className="text-xs font-medium text-gray-700 truncate" title={label}>
          {label}
        </span>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {/* Open in new tab */}
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            title="Mở trong tab mới"
            className="p-1.5 rounded text-gray-400 hover:text-brand hover:bg-gray-100 transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
            </svg>
          </a>
          {/* Close */}
          <button
            type="button"
            onClick={onClose}
            title="Đóng"
            className="p-1.5 rounded text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {canEmbed ? (
        <iframe
          src={url}
          className="flex-1 w-full border-0"
          title={label}
          allow="fullscreen"
          onError={() => setIframeError(true)}
        />
      ) : (
        <div className="flex-1 flex items-center justify-center p-8 bg-gray-50">
          <div className="max-w-sm text-center rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="w-12 h-12 mx-auto mb-3 bg-brand/10 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-brand" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
            </div>
            <p className="text-sm font-semibold text-gray-800">
              {isInsecureHttp
                ? 'Tài liệu HTTP không nhúng được'
                : 'Xem tài liệu nguồn'}
            </p>
            <p className="mt-1.5 text-xs leading-relaxed text-gray-500">
              {isInsecureHttp
                ? 'Nguồn này không dùng kết nối HTTPS nên trình duyệt không thể nhúng an toàn.'
                : 'Nhấn nút bên dưới để mở tài liệu gốc trên trang Chính phủ.'}
            </p>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-brand px-4 py-2.5 text-xs font-semibold text-white hover:bg-brand-dark transition shadow-sm"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
              </svg>
              Mở trong tab mới
            </a>
          </div>
        </div>
      )}
    </div>
  )
}
