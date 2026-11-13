import { useLanguage } from '../i18n'

interface Props {
  /** 'dark' sits on the sidebar; 'light' sits on the gray page background. */
  variant?: 'dark' | 'light'
  className?: string
}

export default function LanguageToggle({ variant = 'dark', className = '' }: Props) {
  const { lang, setLang } = useLanguage()
  const track = variant === 'dark' ? 'bg-white/10' : 'bg-gray-200'
  const inactive =
    variant === 'dark' ? 'text-gray-400 hover:text-white' : 'text-gray-500 hover:text-gray-800'
  return (
    <div className={`inline-flex items-center gap-0.5 p-0.5 rounded-md ${track} ${className}`}>
      {(['vi', 'en'] as const).map((l) => (
        <button
          key={l}
          type="button"
          onClick={() => setLang(l)}
          aria-pressed={lang === l}
          className={`px-2 py-1 rounded text-xs font-medium transition ${
            lang === l ? 'bg-brand text-white shadow-sm' : inactive
          }`}
        >
          {l === 'vi' ? 'VI' : 'EN'}
        </button>
      ))}
    </div>
  )
}
