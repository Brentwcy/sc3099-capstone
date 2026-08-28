'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { ProtectedRoute } from '@/components/protected-route'
import { dashboardDataService } from '@/lib/api/dashboard-data-service'
import type { AttendanceRecord, AttendanceStatus } from '@/types/dashboard'

type HistoryFilter = 'all' | AttendanceStatus

const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-SG', {
  day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
}).format(new Date(value))

const statusStyles: Record<AttendanceStatus, string> = {
  approved: 'bg-emerald-100 text-emerald-800',
  'pending-review': 'bg-amber-100 text-amber-900',
  rejected: 'bg-red-100 text-red-800',
}

const statusLabels: Record<AttendanceStatus, string> = {
  approved: 'Approved',
  'pending-review': 'Pending review',
  rejected: 'Rejected',
}

export default function HistoryPage() {
  const [records, setRecords] = useState<AttendanceRecord[]>([])
  const [filter, setFilter] = useState<HistoryFilter>('all')
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    dashboardDataService.getRecentAttendance(50)
      .then((attendance) => { if (active) setRecords(attendance) })
      .catch(() => { if (active) setError('Attendance history could not be loaded. Please try again later.') })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false }
  }, [])

  const filteredRecords = useMemo(
    () => filter === 'all' ? records : records.filter((record) => record.status === filter),
    [filter, records],
  )
  const approvedCount = records.filter((record) => record.status === 'approved').length
  const reviewCount = records.filter((record) => record.status === 'pending-review').length
  const rejectedCount = records.filter((record) => record.status === 'rejected').length

  return (
    <ProtectedRoute>
      <AppShell>
        <section className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="eyebrow">Your records</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Attendance history</h1>
            <p className="mt-2 text-slate-600">Review attendance submissions made from your student account.</p>
          </div>
          <Link className="button-secondary" href="/dashboard">Back to dashboard</Link>
        </section>

        {!isLoading && !error && records.length > 0 && (
          <section className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Attendance summary">
            <div className="card"><p className="text-sm text-slate-500">Submitted</p><p className="mt-2 text-2xl font-bold text-slate-950">{records.length}</p></div>
            <div className="card"><p className="text-sm text-slate-500">Approved</p><p className="mt-2 text-2xl font-bold text-emerald-700">{approvedCount}</p></div>
            <div className="card"><p className="text-sm text-slate-500">Pending review</p><p className="mt-2 text-2xl font-bold text-amber-700">{reviewCount}</p></div>
            <div className="card"><p className="text-sm text-slate-500">Rejected</p><p className="mt-2 text-2xl font-bold text-red-700">{rejectedCount}</p></div>
          </section>
        )}

        <section className="card mt-8">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <h2 className="text-xl font-semibold text-slate-950">Submitted attendance</h2>
            <div className="flex flex-wrap gap-2" aria-label="Filter attendance history">
              {([
                ['all', 'All'],
                ['approved', 'Approved'],
                ['pending-review', 'Pending review'],
                ['rejected', 'Rejected'],
              ] as const).map(([value, label]) => (
                <button key={value} type="button" className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${filter === value ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>
              ))}
            </div>
          </div>

          {isLoading ? (
            <p className="mt-6 text-sm text-slate-500">Loading attendance history…</p>
          ) : error ? (
            <div className="mt-6 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</div>
          ) : records.length === 0 ? (
            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-6"><h3 className="font-semibold text-slate-950">No attendance records yet</h3><p className="mt-2 text-sm text-slate-600">Completed check-in submissions will appear here.</p></div>
          ) : filteredRecords.length === 0 ? (
            <p className="mt-6 text-sm text-slate-600">No records match this filter.</p>
          ) : (
            <div className="mt-6 overflow-hidden rounded-xl border border-slate-200">
              <div className="hidden grid-cols-[minmax(15rem,2fr)_1.1fr_0.8fr_0.8fr] gap-4 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500 lg:grid">
                <span>Course</span><span>Date</span><span>Session</span><span>Status</span>
              </div>
              {filteredRecords.map((record) => (
                <article key={record.id} className="grid gap-3 border-t border-slate-200 p-4 first:border-t-0 lg:grid-cols-[minmax(15rem,2fr)_1.1fr_0.8fr_0.8fr] lg:items-center">
                  <div><p className="font-semibold text-slate-950">{record.courseCode} {record.courseName}</p><p className="mt-1 text-xs text-slate-500">{record.instructor}</p></div>
                  <div><p className="text-xs text-slate-500 lg:hidden">Date</p><p className="mt-1 whitespace-nowrap text-sm text-slate-800 lg:mt-0">{formatDateTime(record.occurredAt)}</p></div>
                  <div><p className="text-xs text-slate-500 lg:hidden">Session</p><p className="mt-1 text-sm text-slate-800 lg:mt-0">{record.sessionType}</p></div>
                  <div><p className="text-xs text-slate-500 lg:hidden">Status</p><span className={`mt-1 inline-flex rounded-full px-3 py-1 text-xs font-semibold lg:mt-0 ${statusStyles[record.status]}`}>{statusLabels[record.status]}</span></div>
                </article>
              ))}
            </div>
          )}
        </section>
      </AppShell>
    </ProtectedRoute>
  )
}
