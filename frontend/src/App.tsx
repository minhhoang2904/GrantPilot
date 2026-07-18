import { useEffect, useState } from 'react'
import type { Company } from './types'
import { getEmail, isTokenValid, clearSession } from './auth'
import { getCompany } from './api'
import LoginPage from './pages/LoginPage'
import OnboardingPage from './pages/OnboardingPage'
import MainPage from './pages/MainPage'

type View = 'loading' | 'login' | 'onboarding' | 'main'

function profileIsReady(company: Company) {
  const required = [
    company.company_name,
    company.sector,
    company.primary_business_activity_group,
    company.legal_form,
    company.social_insurance_employees,
    company.annual_revenue_vnd,
    company.total_capital_vnd,
    company.first_business_registration_date,
    company.business_description,
    company.province_name,
  ]
  return company.profile_schema_version === 'company-profile-v1'
    && required.every((value) => value !== null && value !== undefined && value !== '')
    && company.has_public_offering !== null && company.has_public_offering !== undefined
    && company.has_business_registration !== null && company.has_business_registration !== undefined
    && company.has_coworking_contract !== null && company.has_coworking_contract !== undefined
    && (company.has_coworking_contract !== true || company.coworking_monthly_cost_vnd != null)
}

export default function App() {
  const [view, setView] = useState<View>('loading')
  const [email, setEmail] = useState<string>('')
  const [company, setCompany] = useState<Company | null>(null)

  async function checkCompany(emailAddr: string) {
    setView('loading')
    try {
      const c = await getCompany(emailAddr)
      if (c && profileIsReady(c)) {
        setCompany(c)
        setView('main')
      } else {
        setView('onboarding')
      }
    } catch {
      // Server unreachable or error — proceed to onboarding so user isn't stuck
      setView('onboarding')
    }
  }

  useEffect(() => {
    const stored = getEmail()
    if (!stored || !isTokenValid()) {
      clearSession()
      setView('login')
      return
    }
    setEmail(stored)
    void checkCompany(stored)
  }, [])

  function handleLogin(addr: string) {
    setEmail(addr)
    void checkCompany(addr)
  }

  function handleOnboardingComplete(c: Company) {
    setCompany(c)
    setView('main')
  }

  function handleLogout() {
    clearSession()
    setEmail('')
    setCompany(null)
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
    return <OnboardingPage email={email} onComplete={handleOnboardingComplete} />
  }

  return <MainPage email={email} company={company!} onLogout={handleLogout} />
}
