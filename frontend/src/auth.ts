const TOKEN_KEY = 'gp_token'
const EMAIL_KEY = 'gp_email'

// ── token store ───────────────────────────────────────────────────────────────

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getEmail(): string | null {
  return localStorage.getItem(EMAIL_KEY)
}

export function setSession(token: string, email: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(EMAIL_KEY, email)
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(EMAIL_KEY)
}

// ── token validation (client-side expiry check) ───────────────────────────────

export function isTokenValid(): boolean {
  const token = getToken()
  if (!token) return false
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    // exp is in seconds (Unix timestamp)
    return typeof payload.exp === 'number' && payload.exp > Date.now() / 1000
  } catch {
    return false
  }
}
