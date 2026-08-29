'use client'

import { useEffect, useMemo, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { ProtectedRoute } from '@/components/protected-route'
import { dashboardDataService } from '@/lib/api/dashboard-data-service'
import type { AttendanceRecord, AttendanceStatus } from '@/types/dashboard'

type HistoryFilter = 'all' | 'approved' | 'in-progress' | 'rejected'

const inProgressStatuses: AttendanceStatus[] = ['pending', 'flagged', 'appealed']

const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-SG', {
  day: 'numeric', month: 'short', year: 'numeric', hour: 'numeric', minute: '2-digit',
}).format(new Date(value))

const statusStyles: Record<AttendanceStatus, string> = {
  pending: 'bg-blue-100 text-blue-800',
  approved: 'bg-emerald-100 text-emerald-800',
  flagged: 'bg-amber-100 text-amber-900',
  rejected: 'bg-red-100 text-red-800',
  appealed: 'bg-violet-100 text-violet-800',
}

const statusLabels: Record<AttendanceStatus, string> = {
  pending: 'Processing',
  approved: 'Approved',
  flagged: 'Under review',
  rejected: 'Rejected',
  appealed: 'Appeal submitted',
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

  const filteredRecords = useMemo(() => records.filter((record) => {
    if (filter === 'all') return true
    if (filter === 'in-progress') return inProgressStatuses.includes(record.status)
    return record.status === filter
  }), [filter, records])
  const approvedCount = records.filter((record) => record.status === 'approved').length
  const inProgressCount = records.filter((record) => inProgressStatuses.includes(record.status)).length
  const rejectedCount = records.filter((record) => record.status === 'rejected').length

  const filters: Array<{ value: HistoryFilter; label: string; count: number }> = [
    { value: 'all', label: 'All', count: records.length },
    { value: 'approved', label: 'Approved', count: approvedCount },
    { value: 'in-progress', label: 'In progress', count: inProgressCount },
    { value: 'rejected', label: 'Rejected', count: rejectedCount },
  ]

  return (
    <ProtectedRoute>
      <AppShell>
        <section>
          <p className="eyebrow">Your records</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Attendance history</h1>
          <p className="mt-2 text-slate-600">Review your previous attendance check-ins and their current status.</p>
        </section>

        {!isLoading && !error && records.length > 0 && (
          <p className="mt-6 text-sm font-medium text-slate-600">
            {records.length} {records.length === 1 ? 'check-in' : 'check-ins'} shown
            <span aria-hidden="true"> · </span>
            {inProgressCount} in progress
          </p>
        )}

        <section className="card mt-8">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <h2 className="text-xl font-semibold text-slate-950">Your check-ins</h2>
            <div className="flex flex-wrap gap-2" aria-label="Filter attendance history">
              {filters.map(({ value, label, count }) => (
                <button key={value} type="button" className={`rounded-lg px-3 py-2 text-sm font-semibold transition ${filter === value ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200'}`} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label} {count}</button>
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
                <span>Course</span><span>Session</span><span>Submitted at</span><span>Status</span>
              </div>
              {filteredRecords.map((record) => (
                <article key={record.id} className="grid gap-3 border-t border-slate-200 p-4 first:border-t-0 lg:grid-cols-[minmax(15rem,2fr)_1.1fr_0.8fr_0.8fr] lg:items-center">
                  <div><p className="font-semibold text-slate-950">{record.courseCode}</p></div>
                  <div><p className="text-xs text-slate-500 lg:hidden">Session</p><p className="mt-1 text-sm text-slate-800 lg:mt-0">{record.sessionName}</p></div>
                  <div><p className="text-xs text-slate-500 lg:hidden">Submitted at</p><p className="mt-1 whitespace-nowrap text-sm text-slate-800 lg:mt-0">{formatDateTime(record.checkedInAt)}</p></div>
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
