'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { useAuth } from '@/contexts/auth-context'
import { dashboardDataService } from '@/lib/api/dashboard-data-service'
import type { AttendanceRecord, AttendanceStatus, DashboardSession, SessionAvailability } from '@/types/dashboard'

const formatTime = (value: string) => new Intl.DateTimeFormat('en-SG', { hour: 'numeric', minute: '2-digit' }).format(new Date(value))
const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-SG', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' }).format(new Date(value))

const attendanceStyles: Record<AttendanceStatus, string> = {
  pending: 'bg-blue-100 text-blue-800',
  approved: 'bg-emerald-100 text-emerald-800',
  flagged: 'bg-amber-100 text-amber-900',
  rejected: 'bg-red-100 text-red-800',
  appealed: 'bg-violet-100 text-violet-800',
}

const attendanceLabels: Record<AttendanceStatus, string> = {
  pending: 'Processing',
  approved: 'Approved',
  flagged: 'Under review',
  rejected: 'Rejected',
  appealed: 'Appeal submitted',
}

const activeSessionGrid = 'lg:grid-cols-[2fr_0.75fr_0.65fr_1fr_0.65fr_0.9fr]'
const attendanceGrid = 'lg:grid-cols-[minmax(15rem,2fr)_1.1fr_0.8fr_0.8fr]'

const sessionStyles: Record<SessionAvailability, string> = {
  open: 'bg-emerald-100 text-emerald-800',
  upcoming: 'bg-blue-100 text-blue-800',
  closed: 'bg-slate-100 text-slate-700',
}

const sessionLabels: Record<SessionAvailability, string> = {
  open: 'Open',
  upcoming: 'Upcoming',
  closed: 'Closed',
}

const formatSessionType = (value: DashboardSession['sessionType']) => value.charAt(0).toUpperCase() + value.slice(1)

export default function DashboardPage() {
  const router = useRouter()
  const { user, isLoading } = useAuth()
  const [sessions, setSessions] = useState<DashboardSession[]>([])
  const [attendance, setAttendance] = useState<AttendanceRecord[]>([])
  const [isLoadingDashboard, setIsLoadingDashboard] = useState(true)
  const [dashboardError, setDashboardError] = useState('')

  useEffect(() => {
    if (!isLoading && !user) router.replace('/login')
  }, [isLoading, router, user])

  useEffect(() => {
    let active = true
    const loadDashboard = async () => {
      try {
        const [activeSessions, recentAttendance] = await Promise.all([
          dashboardDataService.getActiveSessions(),
          dashboardDataService.getRecentAttendance(3),
        ])
        if (active) {
          setSessions(activeSessions)
          setAttendance(recentAttendance)
        }
      } catch {
        if (active) setDashboardError('Dashboard records could not be loaded. Please try again later.')
      } finally {
        if (active) setIsLoadingDashboard(false)
      }
    }
    void loadDashboard()
    return () => { active = false }
  }, [])

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

      {dashboardError && <div className="mt-8 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{dashboardError}</div>}

      <section className="card mt-8">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-950">Active sessions</h2>
          <Link className="grid h-10 w-10 place-items-center rounded-lg text-xl text-blue-700 transition hover:bg-blue-50 hover:text-blue-900" href="/sessions" aria-label="View all active sessions">→</Link>
        </div>

        {isLoadingDashboard ? (
          <p className="mt-5 text-sm text-slate-500">Loading active sessions…</p>
        ) : sessions.length === 0 ? (
          <p className="mt-5 text-sm text-slate-600">No active sessions right now.</p>
        ) : (
          <div className="mt-5 overflow-hidden rounded-xl border border-slate-200">
            <div className={`hidden gap-4 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 lg:grid ${activeSessionGrid}`}>
              <span>Course</span><span>Type</span><span>Location</span><span>Time</span><span>Status</span><span>Action</span>
            </div>
            {sessions.map((session) => (
              <article key={session.id} className={`grid gap-4 border-t border-slate-200 p-4 first:border-t-0 lg:items-center ${activeSessionGrid}`}>
                <div><p className="font-semibold text-slate-950">{[session.courseCode, session.courseName].filter(Boolean).join(' ') || 'Course unavailable'}</p><p className="mt-1 text-xs text-slate-500">{session.sessionName}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Type</p><p className="mt-1 text-sm font-medium text-slate-800 lg:mt-0">{formatSessionType(session.sessionType)}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Location</p><p className="mt-1 text-sm text-slate-800 lg:mt-0">{session.venueName ?? 'Not specified'}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Time</p><p className="mt-1 whitespace-nowrap text-sm text-slate-800 lg:mt-0">{formatTime(session.startsAt)}–{formatTime(session.endsAt)}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Status</p><span className={`mt-1 inline-flex whitespace-nowrap rounded-full px-3 py-1 text-xs font-semibold lg:mt-0 ${sessionStyles[session.availability]}`}>{sessionLabels[session.availability]}</span></div>
                <div>
                  {!setupComplete ? (
                    <Link className="button-secondary w-full whitespace-nowrap lg:w-auto" href={setupHref}>Complete setup</Link>
                  ) : session.availability === 'open' ? (
                    <Link className="button-primary w-full whitespace-nowrap lg:w-auto" href={`/sessions?session=${session.id}`}>Check in</Link>
                  ) : (
                    <span className="whitespace-nowrap text-sm font-medium text-slate-500">{session.availability === 'upcoming' ? 'Not open yet' : 'Closed'}</span>
                  )}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="card mt-8">
        <div className="flex items-center justify-between gap-4">
          <h2 className="text-lg font-semibold text-slate-950">Attendance history</h2>
          <Link className="grid h-10 w-10 place-items-center rounded-lg text-xl text-blue-700 transition hover:bg-blue-50 hover:text-blue-900" href="/history" aria-label="View full attendance history">→</Link>
        </div>

        {isLoadingDashboard ? (
          <p className="mt-5 text-sm text-slate-500">Loading attendance history…</p>
        ) : attendance.length === 0 ? (
          <p className="mt-5 text-sm text-slate-600">No attendance records yet.</p>
        ) : (
          <div className="mt-5 overflow-hidden rounded-xl border border-slate-200">
            <div className={`hidden gap-4 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 lg:grid ${attendanceGrid}`}>
              <span>Course</span><span>Session</span><span>Submitted at</span><span>Status</span>
            </div>
            {attendance.map((record) => (
              <article key={record.id} className={`grid gap-3 border-t border-slate-200 p-4 first:border-t-0 lg:items-center ${attendanceGrid}`}>
                <div><p className="font-semibold text-slate-950">{record.courseCode}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Session</p><p className="mt-1 text-sm text-slate-800 lg:mt-0">{record.sessionName}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Submitted at</p><p className="mt-1 whitespace-nowrap text-sm text-slate-800 lg:mt-0">{formatDateTime(record.checkedInAt)}</p></div>
                <div><p className="text-xs text-slate-500 lg:hidden">Status</p><span className={`mt-1 inline-flex rounded-full px-3 py-1 text-xs font-semibold lg:mt-0 ${attendanceStyles[record.status]}`}>{attendanceLabels[record.status]}</span></div>
              </article>
            ))}
          </div>
        )}
      </section>
    </AppShell>
  )
}
