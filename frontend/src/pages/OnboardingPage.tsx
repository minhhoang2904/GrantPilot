import { useState } from 'react'
import { createCompany, ApiError } from '../api'
import type { Company, Sector } from '../types'

interface Props {
  email: string
  onComplete: (company: Company) => void
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
  labelTrue = 'Có',
  labelFalse = 'Không',
}: {
  value: boolean | null
  onChange: (v: boolean | null) => void
  labelTrue?: string
  labelFalse?: string
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

// ── sector options ────────────────────────────────────────────────────────────
const SECTOR_OPTIONS: { value: Sector; label: string }[] = [
  { value: 'nong_lam_ngu_nghiep', label: 'Nông, lâm, ngư nghiệp' },
  { value: 'cong_nghiep_xay_dung', label: 'Công nghiệp & xây dựng' },
  { value: 'thuong_mai_dich_vu', label: 'Thương mại & dịch vụ' },
]

// ── component ─────────────────────────────────────────────────────────────────
export default function OnboardingPage({ email, onComplete }: Props) {
  // basic
  const [companyName, setCompanyName] = useState('')

  const [sector, setSector] = useState<Sector | ''>('')
  const [siEmployees, setSiEmployees] = useState<string>('')
  const [annualRevenue, setAnnualRevenue] = useState<string>('')
  const [totalCapital, setTotalCapital] = useState<string>('')

  const currentYear = new Date().getFullYear()
  const [foundedYear, setFoundedYear] = useState<string>(String(currentYear - 3))
  const [isPublicOffering, setIsPublicOffering] = useState<boolean | null>(null)
  const [productType, setProductType] = useState('')
  const [hasPatent, setHasPatent] = useState<boolean | null>(null)
  const [province, setProvince] = useState('')
  const [hasCoworkingContract, setHasCoworkingContract] = useState<boolean | null>(null)
  const [hasBusinessRegistration, setHasBusinessRegistration] = useState<boolean | null>(null)
  const [coworkingMonthlyCost, setCoworkingMonthlyCost] = useState<string>('')

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
    if (!companyName.trim())        { setError('Vui lòng nhập tên doanh nghiệp.'); return }
    if (!sector)                    { setError('Vui lòng chọn lĩnh vực hoạt động.'); return }
    if (!siEmployees)               { setError('Vui lòng nhập số lao động đóng BHXH.'); return }
    if (!annualRevenue)             { setError('Vui lòng nhập doanh thu năm.'); return }
    if (!totalCapital)              { setError('Vui lòng nhập tổng vốn.'); return }
    if (!foundedYear)               { setError('Vui lòng nhập năm thành lập.'); return }
    if (!productType.trim())        { setError('Vui lòng nhập loại sản phẩm / dịch vụ.'); return }
    if (isPublicOffering === null)  { setError('Vui lòng chọn trạng thái chào bán chứng khoán.'); return }
    if (hasPatent === null)         { setError('Vui lòng chọn trạng thái bằng sáng chế.'); return }
    if (!province.trim())           { setError('Vui lòng nhập tỉnh / thành phố.'); return }
    if (hasCoworkingContract === null)  { setError('Vui lòng chọn trạng thái hợp đồng coworking.'); return }
    if (hasBusinessRegistration === null) { setError('Vui lòng chọn trạng thái giấy đăng ký kinh doanh.'); return }
    if (hasCoworkingContract && !coworkingMonthlyCost) { setError('Vui lòng nhập chi phí coworking hàng tháng.'); return }
    setError('')
    setSubmitting(true)
    try {
      const payload: Omit<Company, 'created_at' | 'updated_at'> = {
        email,
        company_name: companyName.trim(),
        sector: sector || null,
        social_insurance_employees: siEmployees ? parseInt(siEmployees) : null,
        annual_revenue_vnd: annualRevenue ? parseInt(annualRevenue) : null,
        total_capital_vnd: totalCapital ? parseInt(totalCapital) : null,
        founded_year: foundedYear ? parseInt(foundedYear) : null,
        is_public_offering: isPublicOffering,
        product_type: productType.trim() || null,
        has_patent: hasPatent,
        province: province.trim() || null,
        has_coworking_contract: hasCoworkingContract,
        has_business_registration: hasBusinessRegistration,
        coworking_monthly_cost_vnd: coworkingMonthlyCost ? parseInt(coworkingMonthlyCost) : null,
      }
      const company = await createCompany(payload)
      onComplete(company)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Đã xảy ra lỗi, vui lòng thử lại.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-brand rounded-2xl mb-4 shadow-lg">
            <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Thiết lập hồ sơ doanh nghiệp</h1>
          <p className="mt-2 text-sm text-gray-500">
            Chào mừng <span className="font-medium text-gray-700">{email}</span>. Điền thông tin
            một lần duy nhất — hệ thống dùng để xét điều kiện hưởng ưu đãi.
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">
          <form onSubmit={handleSubmit} className="space-y-5">

            <Field label="Tên doanh nghiệp" required>
              <input
                type="text"
                autoFocus
                required
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Công ty TNHH ABC"
                className={inputCls}
              />
            </Field>

            <Field label="Lĩnh vực hoạt động" required>
              <select
                required
                value={sector}
                onChange={(e) => setSector(e.target.value as Sector)}
                className={inputCls}
              >
                <option value="">— Chọn lĩnh vực —</option>
                {SECTOR_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <Field label="Lao động BHXH" hint="⚠️ BHXH" required>
                <input
                  type="number"
                  min={0}
                  required
                  value={siEmployees}
                  onChange={(e) => setSiEmployees(e.target.value)}
                  placeholder="vd: 45"
                  className={inputCls}
                />
              </Field>
              <Field label="Doanh thu năm (VNĐ)" required>
                <input
                  type="number"
                  min={0}
                  step={1_000_000}
                  required
                  value={annualRevenue}
                  onChange={(e) => setAnnualRevenue(e.target.value)}
                  placeholder="vd: 50000000000"
                  className={inputCls}
                />
                {fmtVnd(annualRevenue) && (
                  <p className="mt-0.5 text-xs text-gray-400">≈ {fmtVnd(annualRevenue)}</p>
                )}
              </Field>
              <Field label="Tổng vốn (VNĐ)" required>
                <input
                  type="number"
                  min={0}
                  step={1_000_000}
                  required
                  value={totalCapital}
                  onChange={(e) => setTotalCapital(e.target.value)}
                  placeholder="vd: 20000000000"
                  className={inputCls}
                />
                {fmtVnd(totalCapital) && (
                  <p className="mt-0.5 text-xs text-gray-400">≈ {fmtVnd(totalCapital)}</p>
                )}
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Năm thành lập" hint="vd: 2019" required>
                <input
                  type="number"
                  min={1900}
                  max={currentYear}
                  required
                  value={foundedYear}
                  onChange={(e) => setFoundedYear(e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="Loại sản phẩm / dịch vụ" required>
                <input
                  type="text"
                  required
                  value={productType}
                  onChange={(e) => setProductType(e.target.value)}
                  placeholder="vd: phần mềm SaaS, thiết bị y tế..."
                  className={inputCls}
                />
              </Field>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Chào bán chứng khoán ra công chúng?" required>
                <TriToggle value={isPublicOffering} onChange={setIsPublicOffering} />
              </Field>
              <Field label="Có bằng sáng chế / patent?" required>
                <TriToggle value={hasPatent} onChange={setHasPatent} />
              </Field>
            </div>

            <Field label="Tỉnh / thành phố" required>
              <input
                type="text"
                required
                value={province}
                onChange={(e) => setProvince(e.target.value)}
                placeholder="vd: Hà Nội, TP. Hồ Chí Minh, Đà Nẵng..."
                className={inputCls}
              />
            </Field>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <Field label="Có hợp đồng thuê coworking?" required>
                <TriToggle value={hasCoworkingContract} onChange={setHasCoworkingContract} />
              </Field>
              <Field label="Có giấy đăng ký kinh doanh?" required>
                <TriToggle value={hasBusinessRegistration} onChange={setHasBusinessRegistration} />
              </Field>
            </div>

            {hasCoworkingContract && (
              <Field label="Chi phí coworking / tháng (VNĐ)" required>
                <input
                  type="number"
                  min={0}
                  step={100_000}
                  required
                  value={coworkingMonthlyCost}
                  onChange={(e) => setCoworkingMonthlyCost(e.target.value)}
                  placeholder="vd: 3000000"
                  className={inputCls}
                />
                {fmtVnd(coworkingMonthlyCost) && (
                  <p className="mt-0.5 text-xs text-gray-400">≈ {fmtVnd(coworkingMonthlyCost)}/tháng</p>
                )}
              </Field>
            )}

            {/* ── Error & Submit ── */}
            {error && (
              <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 bg-brand hover:bg-brand-dark disabled:opacity-60 text-white text-sm font-medium rounded-lg transition focus:outline-none focus:ring-2 focus:ring-brand focus:ring-offset-2"
            >
              {submitting ? 'Đang lưu...' : 'Lưu & bắt đầu tư vấn →'}
            </button>
          </form>
        </div>

        <p className="text-center text-xs text-gray-400 mt-4">
          Bạn có thể cập nhật hồ sơ bất kỳ lúc nào trong phần cài đặt.
        </p>
      </div>
    </div>
  )
}
