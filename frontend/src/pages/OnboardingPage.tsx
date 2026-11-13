import { useState } from 'react'
import { createCompany, updateCompany, ApiError } from '../api'
import type { BusinessActivityGroup, Company, LegalForm, Sector } from '../types'
import { useT } from '../i18n'
import LanguageToggle from '../components/LanguageToggle'

interface Props {
  email: string
  existing?: Company | null
  /** When true, skip is discouraged (eligibility mode) but still allowed to go back */
  required?: boolean
  onComplete: (company: Company) => void
  onSkip: () => void
}

// ── helpers ──────────────────────────────────────────────────────────────────

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string
  hint?: string
  required?: boolean
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">
        {label}
        {required && <span className="ml-0.5 text-red-500">*</span>}
        {hint && <span className="ml-1.5 text-xs font-normal text-gray-400">({hint})</span>}
      </label>
      {children}
    </div>
  )
}

const inputCls =
  'w-full px-3 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-brand focus:border-transparent transition'

/**
 * TriToggle — 3 states: null (unknown) / true / false
 */
function TriToggle({
  value,
  onChange,
  labelTrue,
  labelFalse,
}: {
  value: boolean | null
  onChange: (v: boolean | null) => void
  labelTrue: string
  labelFalse: string
}) {
  const btn = (label: string, active: boolean, click: () => void, color: string) => (
    <button
      type="button"
      onClick={click}
      className={`flex-1 py-1.5 text-xs font-medium rounded-md transition ${
        active ? `${color} text-white shadow-sm` : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
      }`}
    >
      {label}
    </button>
  )
  return (
    <div className="flex gap-1 mt-1">
      {btn(labelTrue, value === true, () => onChange(value === true ? null : true), 'bg-brand')}
      {btn(labelFalse, value === false, () => onChange(value === false ? null : false), 'bg-gray-500')}
    </div>
  )
}

import type { TranslationKey } from '../i18n/types'

// ── sector options ────────────────────────────────────────────────────────────
const SECTOR_OPTIONS: { value: Sector; labelKey: TranslationKey }[] = [
  { value: 'nong_lam_ngu_nghiep', labelKey: 'onboarding.sectorAgri' },
  { value: 'cong_nghiep_xay_dung', labelKey: 'onboarding.sectorIndustry' },
  { value: 'thuong_mai_dich_vu', labelKey: 'onboarding.sectorTrade' },
]

const OTHER_ACTIVITY_KEY: TranslationKey = 'onboarding.activityOther'
const ACTIVITY_OPTIONS: Record<Sector, { value: BusinessActivityGroup; labelKey: TranslationKey }[]> = {
  nong_lam_ngu_nghiep: [
    { value: 'agriculture', labelKey: 'onboarding.activityAgriculture' },
    { value: 'forestry', labelKey: 'onboarding.activityForestry' },
    { value: 'fisheries', labelKey: 'onboarding.activityFisheries' },
    { value: 'other', labelKey: OTHER_ACTIVITY_KEY },
  ],
  cong_nghiep_xay_dung: [
    { value: 'manufacturing', labelKey: 'onboarding.activityManufacturing' },
    { value: 'processing', labelKey: 'onboarding.activityProcessing' },
    { value: 'construction', labelKey: 'onboarding.activityConstruction' },
    { value: 'other', labelKey: OTHER_ACTIVITY_KEY },
  ],
  thuong_mai_dich_vu: [
    { value: 'trade', labelKey: 'onboarding.activityTrade' },
    { value: 'services', labelKey: 'onboarding.activityServices' },
    { value: 'other', labelKey: OTHER_ACTIVITY_KEY },
  ],
}

const LEGAL_FORM_OPTIONS: { value: LegalForm; labelKey: TranslationKey }[] = [
  { value: 'limited_liability_company', labelKey: 'onboarding.legalLimitedLiability' },
  { value: 'joint_stock_company', labelKey: 'onboarding.legalJointStock' },
  { value: 'partnership', labelKey: 'onboarding.legalPartnership' },
  { value: 'private_enterprise', labelKey: 'onboarding.legalPrivate' },
  { value: 'cooperative', labelKey: 'onboarding.legalCooperative' },
  { value: 'household_business', labelKey: 'onboarding.legalHousehold' },
  { value: 'other', labelKey: 'onboarding.legalOther' },
]

function numStr(v?: number | null) {
  return v != null ? String(v) : ''
}

// ── component ─────────────────────────────────────────────────────────────────
export default function OnboardingPage({
  email,
  existing,
  required = false,
  onComplete,
  onSkip,
}: Props) {
  const t = useT()
  const isEdit = Boolean(existing)

  const [companyName, setCompanyName] = useState(existing?.company_name ?? '')
  const [sector, setSector] = useState<Sector | ''>(existing?.sector ?? '')
  const [activityGroup, setActivityGroup] = useState<BusinessActivityGroup | ''>(
    existing?.primary_business_activity_group ?? '',
  )
  const [legalForm, setLegalForm] = useState<LegalForm | ''>(existing?.legal_form ?? '')
  const [siEmployees, setSiEmployees] = useState<string>(numStr(existing?.social_insurance_employees))
  const [annualRevenue, setAnnualRevenue] = useState<string>(numStr(existing?.annual_revenue_vnd))
  const [totalCapital, setTotalCapital] = useState<string>(numStr(existing?.total_capital_vnd))

  const [registrationDate, setRegistrationDate] = useState(
    existing?.first_business_registration_date ?? '',
  )
  const [hasPublicOffering, setHasPublicOffering] = useState<boolean | null>(
    existing?.has_public_offering ?? null,
  )
  const [businessDescription, setBusinessDescription] = useState(existing?.business_description ?? '')
  const [provinceName, setProvinceName] = useState(existing?.province_name ?? '')
  const [provinceCode, setProvinceCode] = useState(existing?.province_code ?? '')
  const [hasCoworkingContract, setHasCoworkingContract] = useState<boolean | null>(
    existing?.has_coworking_contract ?? null,
  )
  const [hasBusinessRegistration, setHasBusinessRegistration] = useState<boolean | null>(
    existing?.has_business_registration ?? null,
  )
  const [coworkingMonthlyCost, setCoworkingMonthlyCost] = useState<string>(
    numStr(existing?.coworking_monthly_cost_vnd),
  )
  const [hasStateCapital, setHasStateCapital] = useState<boolean | null>(
    existing?.has_state_capital ?? null,
  )
  const [hasForeignCapital, setHasForeignCapital] = useState<boolean | null>(
    existing?.has_foreign_investment_capital ?? null,
  )
  const [hasCollateral, setHasCollateral] = useState<boolean | null>(
    existing?.has_collateral ?? null,
  )
  const [hasReceivedInterestSupport, setHasReceivedInterestSupport] = useState<boolean | null>(
    existing?.has_received_same_interest_support ?? null,
  )

  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  function fmtVnd(v: string) {
    const n = Number(v)
    if (!v || isNaN(n) || n <= 0) return null
    return new Intl.NumberFormat('vi-VN', {
      style: 'currency',
      currency: 'VND',
      notation: 'compact',
      maximumFractionDigits: 1,
    }).format(n)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!companyName.trim())        { setError(t('onboarding.errorCompanyName')); return }
    if (!sector)                    { setError(t('onboarding.errorSector')); return }
    if (!activityGroup)             { setError(t('onboarding.errorActivityGroup')); return }
    if (!legalForm)                 { setError(t('onboarding.errorLegalForm')); return }
    if (!siEmployees)               { setError(t('onboarding.errorSiEmployees')); return }
    if (!annualRevenue)             { setError(t('onboarding.errorAnnualRevenue')); return }
    if (!totalCapital)              { setError(t('onboarding.errorTotalCapital')); return }
    if (!registrationDate)          { setError(t('onboarding.errorRegistrationDate')); return }
    if (!businessDescription.trim()) { setError(t('onboarding.errorBusinessDescription')); return }
    if (hasPublicOffering === null) { setError(t('onboarding.errorPublicOffering')); return }
    if (!provinceName.trim())       { setError(t('onboarding.errorProvinceName')); return }
    if (hasCoworkingContract === null)  { setError(t('onboarding.errorCoworkingContract')); return }
    if (hasBusinessRegistration === null) { setError(t('onboarding.errorBusinessRegistration')); return }
    if (hasCoworkingContract && !coworkingMonthlyCost) { setError(t('onboarding.errorCoworkingCost')); return }
    setError('')
    setSubmitting(true)
    try {
      const payload = {
        company_name: companyName.trim(),
        sector: sector || null,
        primary_business_activity_group: activityGroup || null,
        legal_form: legalForm || null,
        province_code: provinceCode.trim() || null,
        province_name: provinceName.trim() || null,
        business_description: businessDescription.trim() || null,
        social_insurance_employees: siEmployees ? parseInt(siEmployees) : null,
        annual_revenue_vnd: annualRevenue ? parseInt(annualRevenue) : null,
        total_capital_vnd: totalCapital ? parseInt(totalCapital) : null,
        first_business_registration_date: registrationDate || null,
        has_public_offering: hasPublicOffering,
        has_coworking_contract: hasCoworkingContract,
        has_business_registration: hasBusinessRegistration,
        coworking_monthly_cost_vnd:
          hasCoworkingContract && coworkingMonthlyCost ? parseInt(coworkingMonthlyCost) : null,
        has_state_capital: hasStateCapital,
        has_foreign_investment_capital: hasForeignCapital,
        has_collateral: hasCollateral,
        has_received_same_interest_support: hasReceivedInterestSupport,
      }
      const company = isEdit
        ? await updateCompany(email, payload)
        : await createCompany({ email, ...payload })
      onComplete(company)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t('common.error'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12 relative">
      <div className="absolute top-4 right-4">
        <LanguageToggle variant="light" />
      </div>
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand rounded-2xl mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">
            {isEdit ? t('onboarding.titleEdit') : t('onboarding.titleNew')}
          </h1>
          <p className="mt-2 text-sm text-gray-500">
            {required ? (
              t('onboarding.subtitleRequired')
            ) : (
              t('onboarding.subtitleOptional')
            )}
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">

            <Field label={t('onboarding.labelCompanyName')} required>
              <input
                type="text"
                autoFocus
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder={t('onboarding.placeholderCompanyName')}
                className={inputCls}
              />
            </Field>

            <Field label={t('onboarding.labelSector')} required>
              <select
                required
                value={sector}
                onChange={(e) => {
                  setSector(e.target.value as Sector)
                  setActivityGroup('')
                }}
                className={inputCls}
              >
                <option value="">{t('onboarding.placeholderSector')}</option>
                {SECTOR_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{t(o.labelKey)}</option>
                ))}
              </select>
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label={t('onboarding.labelActivityGroup')} required>
                <select
                  required
                  disabled={!sector}
                  value={activityGroup}
                  onChange={(e) => setActivityGroup(e.target.value as BusinessActivityGroup)}
                  className={inputCls}
                >
                  <option value="">{t('onboarding.placeholderActivityGroup')}</option>
                  {(sector ? (ACTIVITY_OPTIONS[sector] ?? []) : []).map((o) => (
                    <option key={o.value} value={o.value}>{t(o.labelKey)}</option>
                  ))}
                </select>
              </Field>
              <Field label={t('onboarding.labelLegalForm')} required>
                <select
                  required
                  value={legalForm}
                  onChange={(e) => setLegalForm(e.target.value as LegalForm)}
                  className={inputCls}
                >
                  <option value="">{t('onboarding.placeholderLegalForm')}</option>
                  {LEGAL_FORM_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>{t(o.labelKey)}</option>
                  ))}
                </select>
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Field label={t('onboarding.labelSiEmployees')} hint={t('onboarding.hintSiEmployees')} required>
                <input
                  type="number"
                  min={0}
                  required
                  value={siEmployees}
                  onChange={(e) => setSiEmployees(e.target.value)}
                  placeholder={t('onboarding.placeholderSiEmployees')}
                  className={inputCls}
                />
              </Field>
              <Field label={t('onboarding.labelAnnualRevenue')} required>
                <input
                  type="number"
                  min={0}
                  step={1_000_000}
                  required
                  value={annualRevenue}
                  onChange={(e) => setAnnualRevenue(e.target.value)}
                  placeholder={t('onboarding.placeholderAnnualRevenue')}
                  className={inputCls}
                />
                {fmtVnd(annualRevenue) && (
                  <p className="mt-0.5 text-xs text-gray-400">≈ {fmtVnd(annualRevenue)}</p>
                )}
              </Field>
              <Field label={t('onboarding.labelTotalCapital')} required>
                <input
                  type="number"
                  min={0}
                  step={1_000_000}
                  required
                  value={totalCapital}
                  onChange={(e) => setTotalCapital(e.target.value)}
                  placeholder={t('onboarding.placeholderTotalCapital')}
                  className={inputCls}
                />
                {fmtVnd(totalCapital) && (
                  <p className="mt-0.5 text-xs text-gray-400">≈ {fmtVnd(totalCapital)}</p>
                )}
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label={t('onboarding.labelRegistrationDate')} required>
                <input
                  type="date"
                  max={new Date().toISOString().slice(0, 10)}
                  required
                  value={registrationDate}
                  onChange={(e) => setRegistrationDate(e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label={t('onboarding.labelBusinessDescription')} required>
                <input
                  type="text"
                  required
                  value={businessDescription}
                  onChange={(e) => setBusinessDescription(e.target.value)}
                  placeholder={t('onboarding.placeholderBusinessDescription')}
                  className={inputCls}
                />
              </Field>
            </div>

            <Field label={t('onboarding.labelPublicOffering')} required>
              <TriToggle
                value={hasPublicOffering}
                onChange={setHasPublicOffering}
                labelTrue={t('common.yes')}
                labelFalse={t('common.no')}
              />
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div className="sm:col-span-2">
                <Field label={t('onboarding.labelProvinceName')} required>
                  <input
                    type="text"
                    required
                    value={provinceName}
                    onChange={(e) => setProvinceName(e.target.value)}
                    placeholder={t('onboarding.placeholderProvinceName')}
                    className={inputCls}
                  />
                </Field>
              </div>
              <Field label={t('onboarding.labelProvinceCode')} hint={t('onboarding.hintProvinceCode')}>
                <input
                  type="text"
                  value={provinceCode}
                  onChange={(e) => setProvinceCode(e.target.value)}
                  placeholder={t('onboarding.placeholderProvinceCode')}
                  className={inputCls}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label={t('onboarding.labelCoworkingContract')} required>
                <TriToggle
                  value={hasCoworkingContract}
                  onChange={setHasCoworkingContract}
                  labelTrue={t('common.yes')}
                  labelFalse={t('common.no')}
                />
              </Field>
              <Field label={t('onboarding.labelBusinessRegistration')} required>
                <TriToggle
                  value={hasBusinessRegistration}
                  onChange={setHasBusinessRegistration}
                  labelTrue={t('common.yes')}
                  labelFalse={t('common.no')}
                />
              </Field>
            </div>

            {hasCoworkingContract && (
              <Field label={t('onboarding.labelCoworkingCost')} required>
                <input
                  type="number"
                  min={0}
                  step={100_000}
                  required
                  value={coworkingMonthlyCost}
                  onChange={(e) => setCoworkingMonthlyCost(e.target.value)}
                  placeholder={t('onboarding.placeholderCoworkingCost')}
                  className={inputCls}
                />
                {fmtVnd(coworkingMonthlyCost) && (
                  <p className="mt-0.5 text-xs text-gray-400">≈ {fmtVnd(coworkingMonthlyCost)}{t('common.perMonth')}</p>
                )}
              </Field>
            )}

            <div className="border-t border-gray-100 pt-5">
              <p className="text-sm font-medium text-gray-700 mb-3">{t('onboarding.additionalInfo')}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <Field label={t('onboarding.labelStateCapital')}>
                  <TriToggle value={hasStateCapital} onChange={setHasStateCapital} labelTrue={t('common.yes')} labelFalse={t('common.no')} />
                </Field>
                <Field label={t('onboarding.labelForeignCapital')}>
                  <TriToggle value={hasForeignCapital} onChange={setHasForeignCapital} labelTrue={t('common.yes')} labelFalse={t('common.no')} />
                </Field>
                <Field label={t('onboarding.labelCollateral')}>
                  <TriToggle value={hasCollateral} onChange={setHasCollateral} labelTrue={t('common.yes')} labelFalse={t('common.no')} />
                </Field>
                <Field label={t('onboarding.labelInterestSupport')}>
                  <TriToggle value={hasReceivedInterestSupport} onChange={setHasReceivedInterestSupport} labelTrue={t('common.yes')} labelFalse={t('common.no')} />
                </Field>
              </div>
            </div>

            {/* ── Error & Submit ── */}
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <div className="flex flex-col sm:flex-row gap-3">
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-60 text-white text-sm font-medium rounded-lg transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
              >
                {submitting
                  ? t('common.saving')
                  : isEdit
                    ? t('onboarding.submitSave')
                    : t('onboarding.submitNew')}
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={onSkip}
                className="flex-1 py-2.5 px-4 border border-gray-300 hover:bg-gray-50 disabled:opacity-60 text-gray-700 text-sm font-medium rounded-lg transition"
              >
                {required ? t('onboarding.skipBack') : t('onboarding.skipOptional')}
              </button>
            </div>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          {t('onboarding.skipNote')}
        </p>
      </div>
    </div>
  )
}
