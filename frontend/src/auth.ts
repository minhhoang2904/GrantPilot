const KEY = 'mock_email'

export function getEmail(): string | null {
  return localStorage.getItem(KEY)
}

export function setEmail(email: string): void {
  localStorage.setItem(KEY, email)
}

export function clearEmail(): void {
  localStorage.removeItem(KEY)
}
