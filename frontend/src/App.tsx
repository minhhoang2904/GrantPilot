import { useEffect, useState } from 'react'
import type { Company } from './types'
import { getEmail, isTokenValid, clearSession } from './auth'
import { getCompany } from './api'
import LoginPage from './pages/LoginPage'
import OnboardingPage from './pages/OnboardingPage'
import MainPage from './pages/MainPage'

type View = 'loading' | 'login' | 'onboarding' | 'main'

export default function App() {
  const [view, setView] = useState<View>('loading')
  const [email, setEmail] = useState<string>('')
  const [company, setCompany] = useState<Company | null>(null)
  /** When true, onboarding was opened because eligibility mode requires a profile */
  const [onboardingRequired, setOnboardingRequired] = useState(false)

  async function loadCompanyThenMain(emailAddr: string) {
    setView('loading')
    try {
      const c = await getCompany(emailAddr)
      setCompany(c)
    } catch {
      setCompany(null)
    }
    setView('main')
  }

  useEffect(() => {
    const stored = getEmail()
    if (!stored || !isTokenValid()) {
      clearSession()
      setView('login')
      return
    }
    setEmail(stored)
    void loadCompanyThenMain(stored)
  }, [])

  function handleLogin(addr: string) {
    setEmail(addr)
    void loadCompanyThenMain(addr)
  }

  function handleOnboardingComplete(c: Company) {
    setCompany(c)
    if (onboardingRequired) {
      try {
        localStorage.setItem('gp_chat_mode', 'advisory')
      } catch {
        /* ignore */
      }
    }
    setOnboardingRequired(false)
    setView('main')
  }

  function handleOnboardingSkip() {
    try {
      localStorage.setItem('gp_chat_mode', 'lookup')
    } catch {
      /* ignore */
    }
    setOnboardingRequired(false)
    setView('main')
  }

  function openOnboarding(required = false) {
    setOnboardingRequired(required)
    setView('onboarding')
  }

  function handleLogout() {
    clearSession()
    setEmail('')
    setCompany(null)
    setOnboardingRequired(false)
    setView('login')
  }

  if (view === 'loading') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-2 border-brand border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500">Đang tải...</p>
        </div>
      </div>
    )
  }

  if (view === 'login') {
    return <LoginPage onLogin={handleLogin} />
  }

  if (view === 'onboarding') {
    return (
      <OnboardingPage
        email={email}
        existing={company}
        required={onboardingRequired}
        onComplete={handleOnboardingComplete}
        onSkip={handleOnboardingSkip}
      />
    )
  }

  return (
    <MainPage
      email={email}
      company={company}
      onLogout={handleLogout}
      onOpenOnboarding={(required) => openOnboarding(required)}
    />
  )
}
