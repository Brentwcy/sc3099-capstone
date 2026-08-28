import { apiClient } from '@/lib/api/client'
import type { AttendanceRecord, DashboardDataService, DashboardSession } from '@/types/dashboard'

const minutesFromNow = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()
const daysAgo = (days: number, hour: number, minute: number) => {
  const date = new Date()
  date.setDate(date.getDate() - days)
  date.setHours(hour, minute, 0, 0)
  return date.toISOString()
}

const mockSessions: DashboardSession[] = [
  {
    id: 'session-sc3099-tutorial-1',
    courseCode: 'SC3099',
    courseName: 'Capstone Project',
    instructor: 'Dr Tan Wei Ming',
    sessionName: 'Tutorial',
    location: 'TR+12',
    startsAt: minutesFromNow(-15),
    endsAt: minutesFromNow(45),
    availability: 'open',
  },
]

const mockAttendance: AttendanceRecord[] = [
  { id: 'attendance-1', courseCode: 'SC2006', courseName: 'Software Engineering', instructor: 'Dr Tan Wei Ming', occurredAt: daysAgo(2, 14, 30), sessionType: 'Tutorial', status: 'approved' },
  { id: 'attendance-2', courseCode: 'SC2001', courseName: 'Algorithms', instructor: 'Prof Lim Chen Wei', occurredAt: daysAgo(4, 10, 30), sessionType: 'Lecture', status: 'pending-review' },
  { id: 'attendance-3', courseCode: 'SC2203', courseName: 'Automata Theory', instructor: 'Dr Sarah Lee', occurredAt: daysAgo(6, 13, 30), sessionType: 'Tutorial', status: 'rejected' },
]

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export const mockDashboardDataService: DashboardDataService = {
  async getActiveSessions() {
    await wait(250)
    return mockSessions
  },
  async getRecentAttendance(limit = 3) {
    await wait(250)
    return mockAttendance.slice(0, limit)
  },
}

export const httpDashboardDataService: DashboardDataService = {
  async getActiveSessions() {
    const { data } = await apiClient.get<DashboardSession[]>('/sessions/active')
    return data
  },
  async getRecentAttendance(limit = 3) {
    const { data } = await apiClient.get<AttendanceRecord[]>('/checkins/my-checkins', { params: { limit } })
    return data
  },
}

export const dashboardDataService =
  process.env.NEXT_PUBLIC_USE_MOCK_API === 'false' ? httpDashboardDataService : mockDashboardDataService
