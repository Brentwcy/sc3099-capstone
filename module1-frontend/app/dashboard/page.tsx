'use client'

import Link from 'next/link'
import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { useAuth } from '@/contexts/auth-context'

export default function DashboardPage() {
  const router = useRouter()
  const { user, isLoading } = useAuth()

  useEffect(() => {
    if (!isLoading && !user) router.replace('/login')
  }, [isLoading, router, user])

  if (isLoading || !user) {
    return <AppShell><p className="py-20 text-center text-slate-600">Loading your dashboard…</p></AppShell>
  }

  const consentComplete = Boolean(user.camera_consent && user.geolocation_consent)
  const setupComplete = consentComplete && Boolean(user.face_enrolled)
  const setupHref = consentComplete ? '/onboarding/face-enrollment' : '/onboarding/consent'

  return (
    <AppShell>
      <section className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">Student dashboard</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Hello, {user.full_name}</h1>
          <p className="mt-2 text-slate-600">Your Module 1 foundation is running in mock mode.</p>
        </div>
        <span className="w-fit rounded-full bg-emerald-100 px-3 py-1 text-sm font-semibold text-emerald-800">Signed in</span>
      </section>

      {!setupComplete && (
        <section className="mt-8 flex flex-col justify-between gap-4 rounded-2xl border border-amber-200 bg-amber-50 p-6 sm:flex-row sm:items-center">
          <div>
            <h2 className="font-semibold text-amber-950">Complete your account setup</h2>
            <p className="mt-2 text-sm leading-6 text-amber-900">{consentComplete ? 'Your consent is saved. Face enrollment is still required before attendance check-in.' : 'Review camera and location consent before enrolling your face and checking in.'}</p>
          </div>
          <Link className="button-primary shrink-0" href={setupHref}>Continue setup</Link>
        </section>
      )}

      <section className="card mt-8">
        <h2 className="text-lg font-semibold text-slate-950">Authenticated profile</h2>
        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-3">
          <div><dt className="text-slate-500">Email</dt><dd className="mt-1 font-medium text-slate-950">{user.email}</dd></div>
          <div><dt className="text-slate-500">Role</dt><dd className="mt-1 font-medium capitalize text-slate-950">{user.role}</dd></div>
          <div><dt className="text-slate-500">Account</dt><dd className="mt-1 font-medium text-slate-950">{user.is_active ? 'Active' : 'Inactive'}</dd></div>
        </dl>
      </section>

      <Link className="card mt-8 block transition hover:border-blue-300 hover:shadow-md" href="/sessions" aria-label="Open active sessions">
        <div className="flex items-center gap-2 text-blue-700">
          <h2 className="text-lg font-semibold underline decoration-2 underline-offset-4">Active sessions</h2>
          <span className="text-blue-700" aria-hidden="true">→</span>
        </div>
        <p className="mt-5 text-sm text-slate-500">Currently available</p>
        <p className="mt-1 font-medium text-slate-950">Nil</p>
      </Link>

      <Link className="card mt-8 block transition hover:border-blue-300 hover:shadow-md" href="/history" aria-label="Open attendance history">
        <div className="flex items-center gap-2 text-blue-700">
          <h2 className="text-lg font-semibold underline decoration-2 underline-offset-4">Attendance history</h2>
          <span className="text-blue-700" aria-hidden="true">→</span>
        </div>
        <p className="mt-5 text-sm text-slate-500">Recent records</p>
        <p className="mt-1 font-medium text-slate-950">Nil</p>
      </Link>
    </AppShell>
  )
}
