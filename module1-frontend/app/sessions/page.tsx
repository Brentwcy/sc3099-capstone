'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'
import { dashboardDataService } from '@/lib/api/dashboard-data-service'
import { getStoredDiagnostics } from '@/lib/device/permissions'
import type { StoredDeviceDiagnostics } from '@/types/consent'
import type { DashboardSession, SessionAvailability } from '@/types/dashboard'

const formatTime = (value: string) => new Intl.DateTimeFormat('en-SG', { hour: 'numeric', minute: '2-digit' }).format(new Date(value))

const statusStyles: Record<SessionAvailability, string> = {
  open: 'bg-emerald-100 text-emerald-800',
  upcoming: 'bg-blue-100 text-blue-800',
  'checked-in': 'bg-emerald-100 text-emerald-800',
  closed: 'bg-slate-100 text-slate-700',
}

const statusLabels: Record<SessionAvailability, string> = {
  open: 'Open',
  upcoming: 'Upcoming',
  'checked-in': 'Checked in',
  closed: 'Closed',
}

export default function SessionsPage() {
  const { user } = useAuth()
  const [sessions, setSessions] = useState<DashboardSession[]>([])
  const [diagnostics, setDiagnostics] = useState<StoredDeviceDiagnostics>({})
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  const consentComplete = Boolean(user?.camera_consent && user?.geolocation_consent)
  const setupComplete = consentComplete && Boolean(user?.face_enrolled)
  const setupHref = consentComplete ? '/onboarding/face-enrollment' : '/onboarding/consent'
  const diagnosticsPassed = diagnostics.camera?.state === 'granted' && diagnostics.location?.state === 'granted'

  useEffect(() => {
    let active = true
    setDiagnostics(getStoredDiagnostics())
    dashboardDataService.getActiveSessions()
      .then((records) => { if (active) setSessions(records) })
      .catch(() => { if (active) setError('Sessions could not be loaded. Please try again later.') })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [])

  return (
    <ProtectedRoute>
      <AppShell>
        <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">Attendance</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Sessions</h1>
            <p className="mt-2 text-slate-600">Choose an open class session to begin attendance verification.</p>
          </div>
          <Link className="button-secondary" href="/dashboard">Back to dashboard</Link>
        </section>

        {!setupComplete && (
          <section className="mt-8 flex flex-col justify-between gap-4 rounded-2xl border border-amber-200 bg-amber-50 p-6 sm:flex-row sm:items-center">
            <div>
              <h2 className="font-semibold text-amber-950">Complete setup before checking in</h2>
              <p className="mt-2 text-sm leading-6 text-amber-900">{consentComplete ? 'Your consent is saved, but face enrollment is still required.' : 'Camera and location consent must be reviewed before face enrollment.'}</p>
            </div>
            <Link className="button-primary shrink-0" href={setupHref}>Complete setup</Link>
          </section>
        )}

        {setupComplete && !diagnosticsPassed && (
          <section className="mt-8 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
            Device access has not recently been tested. You can <Link className="font-semibold underline" href="/settings">test access in Settings</Link>, and access will be confirmed again when check-in starts.
          </section>
        )}

        <section className="mt-8">
          <h2 className="text-xl font-semibold text-slate-950">Available sessions</h2>
          {isLoading ? (
            <div className="card mt-4 text-sm text-slate-500">Loading sessions…</div>
          ) : error ? (
            <div className="mt-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</div>
          ) : sessions.length === 0 ? (
            <div className="card mt-4"><h3 className="font-semibold text-slate-950">No active sessions right now</h3><p className="mt-2 text-sm text-slate-600">Open sessions created by your instructors will appear here.</p></div>
          ) : (
            <div className="mt-4 space-y-4">
              {sessions.map((session) => (
                <article key={session.id} className="card">
                  <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-3">
                        <h3 className="text-lg font-semibold text-slate-950">{session.courseCode} {session.courseName}</h3>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[session.availability]}`}>{statusLabels[session.availability]}</span>
                      </div>
                      <p className="mt-1 text-sm text-slate-500">{session.instructor}</p>
                      <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-3">
                        <div><dt className="text-slate-500">Session</dt><dd className="mt-1 font-medium text-slate-900">{session.sessionName}</dd></div>
                        <div><dt className="text-slate-500">Location</dt><dd className="mt-1 font-medium text-slate-900">{session.location}</dd></div>
                        <div><dt className="text-slate-500">Time</dt><dd className="mt-1 whitespace-nowrap font-medium text-slate-900">{formatTime(session.startsAt)}–{formatTime(session.endsAt)}</dd></div>
                      </dl>
                    </div>
                    <div className="shrink-0">
                      {!setupComplete ? (
                        <Link className="button-secondary w-full lg:w-auto" href={setupHref}>Complete setup</Link>
                      ) : session.availability === 'open' ? (
                        <Link className="button-primary w-full lg:w-auto" href={`/sessions?session=${session.id}`}>Check in</Link>
                      ) : session.availability === 'checked-in' ? (
                        <p className="text-sm font-semibold text-emerald-700">Checked in{session.checkedInAt ? ` at ${formatTime(session.checkedInAt)}` : ''}</p>
                      ) : (
                        <p className="text-sm font-medium text-slate-500">{session.availability === 'upcoming' ? 'Check-in has not opened' : 'Check-in is closed'}</p>
                      )}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </AppShell>
    </ProtectedRoute>
  )
}
