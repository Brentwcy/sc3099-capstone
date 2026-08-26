import type { User } from '@/types/auth'

export const SESSION_KEY = 'saiv.auth.session'
export const SESSION_CHANGE_EVENT = 'saiv:auth-session-change'

export interface StoredSession {
  accessToken: string
  refreshToken: string
  user: User
}

function isBrowser() {
  return typeof window !== 'undefined'
}

export function getSession(): StoredSession | null {
  if (!isBrowser()) return null

  try {
    const value = window.sessionStorage.getItem(SESSION_KEY)
    return value ? (JSON.parse(value) as StoredSession) : null
  } catch {
    window.sessionStorage.removeItem(SESSION_KEY)
    return null
  }
}

export function setSession(session: StoredSession) {
  if (!isBrowser()) return
  window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session))
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT))
}

export function clearSession() {
  if (!isBrowser()) return
  window.sessionStorage.removeItem(SESSION_KEY)
  window.dispatchEvent(new Event(SESSION_CHANGE_EVENT))
}

export function subscribeToSessionChanges(listener: () => void) {
  if (!isBrowser()) return () => undefined
  window.addEventListener(SESSION_CHANGE_EVENT, listener)
  window.addEventListener('storage', listener)

  return () => {
    window.removeEventListener(SESSION_CHANGE_EVENT, listener)
    window.removeEventListener('storage', listener)
  }
}
