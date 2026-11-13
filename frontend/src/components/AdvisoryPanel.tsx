import { useState } from 'react'
import type { AdvisoryPolicy, AdvisoryResult, EligibilityStatus, Message } from '../types'
import type { TranslationKey } from '../i18n/types'
import { useT } from '../i18n'

const STATUS_CONFIG: Record<EligibilityStatus, { labelKey: TranslationKey; className: string }> = {
  eligible: {
    labelKey: 'advisory.statusEligible',
    className: 'bg-green-100 text-green-800',
  },
  not_eligible: {
    labelKey: 'advisory.statusNotEligible',
    className: 'bg-orange-100 text-orange-700',
  },
  needs_more_information: {
    labelKey: 'advisory.statusNeedsInfo',
    className: 'bg-yellow-100 text-yellow-800',
  },
  manual_review: {
    labelKey: 'advisory.statusManualReview',
    className: 'bg-blue-100 text-blue-700',
  },
}

function StatusBadge({ status }: { status: EligibilityStatus }) {
  const t = useT()
  const cfg = STATUS_CONFIG[status]
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium whitespace-nowrap ${cfg ? cfg.className : 'bg-gray-100 text-gray-600'}`}
    >
      {cfg ? t(cfg.labelKey) : status}
    </span>
  )
}

const FACT_KEY_MAP: Record<string, TranslationKey> = {
  primary_business_activity_group: 'advisory.factActivityGroup',
  sector: 'advisory.factSector',
  legal_form: 'advisory.factLegalForm',
  social_insurance_employees: 'advisory.factSiEmployees',
  annual_revenue_vnd: 'advisory.factAnnualRevenue',
  total_capital_vnd: 'advisory.factTotalCapital',
  first_business_registration_date: 'advisory.factRegistrationDate',
  has_public_offering: 'advisory.factPublicOffering',
  has_business_registration: 'advisory.factBusinessReg',
  is_sme: 'advisory.factIsSme',
}

function FactLabel({ value }: { value: string }) {
  const t = useT()
  const key = FACT_KEY_MAP[value]
  return <>{key ? t(key) : value.replace(/_/g, ' ')}</>
}

function PolicyRow({ policy }: { policy: AdvisoryPolicy }) {
  const t = useT()
  const [open, setOpen] = useState(false)
  const hasMissing = policy.missing_fields.length > 0
  const hasReasons = policy.reasons.length > 0
  const hasRequirements = (policy.application_requirements?.length ?? 0) > 0
  const hasDetails = hasMissing || hasReasons || hasRequirements

  return (
    <div className="border-b border-gray-100 last:border-0 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium text-gray-800 leading-snug">{policy.title}</p>
        </div>
        <StatusBadge status={policy.status} />
      </div>

      {hasDetails && (
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
          {open ? t('advisory.hideDetail') : t('advisory.showDetail')}
        </button>
      )}

      {open && (
        <div className="mt-2 pl-3 border-l-2 border-gray-200 space-y-2">
          {hasMissing && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 mb-1">{t('advisory.missingFieldsLabel')}</p>
              <ul className="space-y-0.5">
                {policy.missing_fields.map((f) => (
                  <li key={f} className="text-xs text-gray-600 flex gap-1.5">
                    <span className="text-yellow-500 mt-0.5">•</span>
                    <span><FactLabel value={f} /></span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasReasons && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 mb-1">{t('advisory.unmetConditionsLabel')}</p>
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
          {hasRequirements && (
            <div>
              <p className="text-[11px] font-semibold text-gray-500 mb-1">{t('advisory.requirementsLabel')}</p>
              <ul className="space-y-0.5">
                {policy.application_requirements!.map((req, i) => (
                  <li key={i} className="text-xs text-gray-600 flex gap-1.5">
                    <span className="text-teal-500 mt-0.5">✓</span>
                    <span>{req}</span>
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
  result?: AdvisoryResult
  coverageStatus?: Message['coverageStatus']
}

export default function AdvisoryPanel({ result, coverageStatus }: Props) {
  const t = useT()
  const hasPolicies = (result?.policies?.length ?? 0) > 0
  const isNotCovered = coverageStatus === 'not_covered' || !hasPolicies

  // Neutral info card when no matching policies found
  if (isNotCovered) {
    return (
      <div className="mt-3 rounded-xl border border-gray-200 overflow-hidden bg-white">
        <div className="px-4 py-3 flex items-start gap-3">
          <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gray-100 flex items-center justify-center mt-0.5">
            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div>
            <p className="text-xs font-semibold text-gray-700 mb-0.5">{t('advisory.notCoveredTitle')}</p>
            <p className="text-xs text-gray-500 leading-relaxed">
              {t('advisory.notCoveredDesc')}
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-3 rounded-xl border border-gray-200 overflow-hidden bg-white">
      <div className="px-4 py-2.5 bg-gray-50 border-b border-gray-200">
        <p className="text-[11px] uppercase tracking-wide font-semibold text-gray-400">
          {t('advisory.sectionLabel')}
        </p>
      </div>
      {result!.explanation && (
        <div className="px-4 py-3 border-b border-gray-100 text-xs text-gray-600 leading-relaxed bg-teal-50/50">
          {result!.explanation}
        </div>
      )}
      <div className="divide-y divide-gray-100">
        {result!.policies.map((p) => (
          <PolicyRow key={p.policy_id} policy={p} />
        ))}
      </div>
    </div>
  )
}
