'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authService } from '@/lib/api/auth-service'
import {
  clearSession as clearStoredSession,
  getSession,
  setSession as setStoredSession,
  StoredSession,
  subscribeToSessionChanges,
} from '@/lib/auth/session-storage'
import type { LoginRequest, RegisterRequest, User } from '@/types/auth'

interface AuthContextValue {
  user: User | null
  accessToken: string | null
  isLoading: boolean
  login(credentials: LoginRequest): Promise<void>
  register(details: RegisterRequest): Promise<void>
  logout(): void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => subscribeToSessionChanges(() => setSession(getSession())), [])

  useEffect(() => {
    let active = true

    const restore = async () => {
      const stored = getSession()
      if (!stored) {
        if (active) setIsLoading(false)
        return
      }

      if (active) setSession(stored)
      try {
        const user = await authService.getCurrentUser(stored.accessToken)
        if (active) setStoredSession({ ...stored, user })
      } catch {
        clearStoredSession()
      } finally {
        if (active) setIsLoading(false)
      }
    }

    void restore()
    return () => { active = false }
  }, [])

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await authService.login(credentials)
    setStoredSession({ accessToken: response.access_token, refreshToken: response.refresh_token, user: response.user })
  }, [])

  const register = useCallback(async (details: RegisterRequest) => {
    await authService.register(details)
    await login({ email: details.email, password: details.password })
  }, [login])

  const logout = useCallback(() => clearStoredSession(), [])

  const value = useMemo<AuthContextValue>(() => ({
    user: session?.user ?? null,
    accessToken: session?.accessToken ?? null,
    isLoading,
    login,
    register,
    logout,
  }), [isLoading, login, logout, register, session])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
