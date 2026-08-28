export const MIN_PASSWORD_LENGTH = 8

export function normalizeEmail(email: string) {
  return email.trim().toLowerCase()
}

export function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export function getPasswordError(password: string, label = 'Password') {
  if (!password) return `${label} is required.`
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `${label} must contain at least ${MIN_PASSWORD_LENGTH} characters.`
  }
  return null
}
