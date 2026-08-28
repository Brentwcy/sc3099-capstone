'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/auth-context'

export function GuestOnlyRoute({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const { user, isLoading } = useAuth()

  useEffect(() => {
    if (!isLoading && user) router.replace('/dashboard')
  }, [isLoading, router, user])

  if (isLoading || user) {
    return <p className="py-20 text-center text-slate-600">Checking your session…</p>
  }

  return <>{children}</>
}
