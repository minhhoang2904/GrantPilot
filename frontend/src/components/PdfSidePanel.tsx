interface Props {
  url: string
  label: string
  onClose: () => void
}

export default function PdfSidePanel({ url, label, onClose }: Props) {
  // Use Google Docs viewer to reliably embed any public PDF without CORS issues
  const viewerSrc = `https://docs.google.com/gview?url=${encodeURIComponent(url)}&embedded=true`
  const isInsecureHttp = url.trim().toLowerCase().startsWith('http://')

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

      {isInsecureHttp ? (
        <div className="flex-1 flex items-center justify-center p-8 bg-gray-50">
          <div className="max-w-sm text-center rounded-xl border border-amber-200 bg-amber-50 p-5">
            <p className="text-sm font-semibold text-amber-900">Không thể xem trước tài liệu HTTP</p>
            <p className="mt-2 text-xs leading-relaxed text-amber-700">
              Nguồn này không dùng kết nối HTTPS nên trình duyệt không thể nhúng an toàn.
            </p>
            <a
              href={url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-4 inline-flex items-center rounded-lg bg-amber-700 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-800 transition"
            >
              Mở trong tab mới
            </a>
          </div>
        </div>
      ) : (
        <iframe
          src={viewerSrc}
          className="flex-1 w-full border-0"
          title={label}
          allow="fullscreen"
        />
      )}
    </div>
  )
}
