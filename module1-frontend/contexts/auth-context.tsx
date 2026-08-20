'use client'

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { authService } from '@/lib/api/auth-service'
import type { LoginRequest, User } from '@/types/auth'

const SESSION_KEY = 'saiv.auth.session'

interface StoredSession {
  accessToken: string
  refreshToken: string
  user: User
}

interface AuthContextValue {
  user: User | null
  accessToken: string | null
  isLoading: boolean
  login(credentials: LoginRequest): Promise<void>
  logout(): void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    try {
      const stored = window.sessionStorage.getItem(SESSION_KEY)
      if (stored) setSession(JSON.parse(stored) as StoredSession)
    } catch {
      window.sessionStorage.removeItem(SESSION_KEY)
    } finally {
      setIsLoading(false)
    }
  }, [])

  const login = useCallback(async (credentials: LoginRequest) => {
    const response = await authService.login(credentials)
    const nextSession: StoredSession = {
      accessToken: response.access_token,
      refreshToken: response.refresh_token,
      user: response.user,
    }
    window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(nextSession))
    setSession(nextSession)
  }, [])

  const logout = useCallback(() => {
    window.sessionStorage.removeItem(SESSION_KEY)
    setSession(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      accessToken: session?.accessToken ?? null,
      isLoading,
      login,
      logout,
    }),
    [isLoading, login, logout, session],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within AuthProvider')
  return context
}
