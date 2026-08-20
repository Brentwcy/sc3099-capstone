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

      <section className="mt-8 grid gap-4 md:grid-cols-3">
        {[
          ['Active sessions', 'Session discovery and selection will be implemented in Week 5.', '/check-in'],
          ['Consent status', 'Camera and geolocation consent will be implemented in Week 4.', '/consent'],
          ['Attendance history', 'Student check-in history follows the core integration.', '/history'],
        ].map(([title, description, href]) => (
          <article key={title} className="card flex flex-col">
            <h2 className="font-semibold text-slate-950">{title}</h2>
            <p className="mt-2 flex-1 text-sm leading-6 text-slate-600">{description}</p>
            <Link className="mt-6 text-sm font-semibold text-blue-700 hover:text-blue-900" href={href}>View area →</Link>
          </article>
        ))}
      </section>

      <section className="card mt-8">
        <h2 className="text-lg font-semibold text-slate-950">Authenticated profile</h2>
        <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-3">
          <div><dt className="text-slate-500">Email</dt><dd className="mt-1 font-medium text-slate-950">{user.email}</dd></div>
          <div><dt className="text-slate-500">Role</dt><dd className="mt-1 font-medium capitalize text-slate-950">{user.role}</dd></div>
          <div><dt className="text-slate-500">Account</dt><dd className="mt-1 font-medium text-slate-950">{user.is_active ? 'Active' : 'Inactive'}</dd></div>
        </dl>
      </section>
    </AppShell>
  )
}
