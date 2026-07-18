interface Props {
  url: string
  label: string
  onClose: () => void
}

export default function PdfSidePanel({ url, label, onClose }: Props) {
  // Use Google Docs viewer to reliably embed any public PDF without CORS issues
  const viewerSrc = `https://docs.google.com/gview?url=${encodeURIComponent(url)}&embedded=true`

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

      {/* PDF iframe */}
      <iframe
        src={viewerSrc}
        className="flex-1 w-full border-0"
        title={label}
        allow="fullscreen"
      />
    </div>
  )
}
