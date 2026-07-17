const EMAIL_KEY = 'gp_email'
const CREDS_KEY = 'gp_creds' // { [email]: hashedPassword } — mock only

export function getEmail(): string | null {
  return localStorage.getItem(EMAIL_KEY)
}

export function setEmail(email: string): void {
  localStorage.setItem(EMAIL_KEY, email)
}

export function clearEmail(): void {
  localStorage.removeItem(EMAIL_KEY)
}

// ── mock credential store ─────────────────────────────────────────────────────

function getCreds(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(CREDS_KEY) || '{}')
  } catch {
    return {}
  }
}

function saveCreds(creds: Record<string, string>) {
  localStorage.setItem(CREDS_KEY, JSON.stringify(creds))
}

export function register(email: string, password: string): boolean {
  const creds = getCreds()
  if (creds[email]) return false          // already exists
  creds[email] = password
  saveCreds(creds)
  setEmail(email)
  return true
}

export function login(email: string, password: string): boolean {
  const creds = getCreds()
  if (creds[email] === undefined) return false   // not registered
  if (creds[email] !== password) return false    // wrong password
  setEmail(email)
  return true
}

export function isRegistered(email: string): boolean {
  return email in getCreds()
}
