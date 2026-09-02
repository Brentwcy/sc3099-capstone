import { apiClient } from '@/lib/api/client'
import { MOCK_CHECKINS_KEY } from '@/lib/api/checkin-service'
import type { StoredMockCheckIn } from '@/types/checkin'
import type { AttendanceRecord, DashboardDataService, DashboardSession } from '@/types/dashboard'

type SessionResponseDto = {
  id: string
  course_code: string | null
  course_name: string | null
  name: string
  session_type: DashboardSession['sessionType']
  status: 'scheduled' | 'active' | 'closed' | 'cancelled'
  scheduled_start: string
  scheduled_end: string
  checkin_opens_at: string
  checkin_closes_at: string
  venue_name: string | null
  require_liveness_check: boolean
  require_face_match: boolean
  qr_code_enabled: boolean
}

type MyCheckInResponseDto = {
  id: string
  session_id: string
  session_name: string
  course_code: string
  status: AttendanceRecord['status']
  checked_in_at: string
  risk_score: number
}

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
    sessionName: 'Capstone Tutorial',
    sessionType: 'tutorial',
    venueName: 'TR+12',
    startsAt: minutesFromNow(-15),
    endsAt: minutesFromNow(45),
    checkinClosesAt: minutesFromNow(30),
    requireLivenessCheck: true,
    requireFaceMatch: true,
    qrCodeEnabled: false,
    availability: 'open',
  },
]

const mockAttendance: AttendanceRecord[] = [
  { id: 'attendance-1', sessionId: 'session-1', courseCode: 'SC2006', sessionName: 'Software Engineering Tutorial', checkedInAt: daysAgo(2, 14, 30), status: 'approved', riskScore: 0.12 },
  { id: 'attendance-2', sessionId: 'session-2', courseCode: 'SC2001', sessionName: 'Algorithms Lecture', checkedInAt: daysAgo(4, 10, 30), status: 'flagged', riskScore: 0.58 },
  { id: 'attendance-3', sessionId: 'session-3', courseCode: 'SC2203', sessionName: 'Automata Theory Tutorial', checkedInAt: daysAgo(6, 13, 30), status: 'rejected', riskScore: 0.84 },
]

const getAvailability = (session: SessionResponseDto): DashboardSession['availability'] => {
  const now = Date.now()
  if (session.status === 'closed' || session.status === 'cancelled' || now > Date.parse(session.checkin_closes_at)) return 'closed'
  if (session.status === 'scheduled' || now < Date.parse(session.checkin_opens_at)) return 'upcoming'
  return 'open'
}

const mapSession = (session: SessionResponseDto): DashboardSession => ({
  id: session.id,
  courseCode: session.course_code,
  courseName: session.course_name,
  sessionName: session.name,
  sessionType: session.session_type,
  venueName: session.venue_name,
  startsAt: session.scheduled_start,
  endsAt: session.scheduled_end,
  checkinClosesAt: session.checkin_closes_at,
  requireLivenessCheck: session.require_liveness_check,
  requireFaceMatch: session.require_face_match,
  qrCodeEnabled: session.qr_code_enabled,
  availability: getAvailability(session),
})

const mapAttendance = (record: MyCheckInResponseDto): AttendanceRecord => ({
  id: record.id,
  sessionId: record.session_id,
  courseCode: record.course_code,
  sessionName: record.session_name,
  checkedInAt: record.checked_in_at,
  status: record.status,
  riskScore: record.risk_score,
})

const wait = (milliseconds: number) => new Promise((resolve) => window.setTimeout(resolve, milliseconds))

export const mockDashboardDataService: DashboardDataService = {
  async getActiveSessions() {
    await wait(250)
    return mockSessions
  },
  async getRecentAttendance(limit = 3) {
    await wait(250)
    let submitted: StoredMockCheckIn[] = []
    try {
      submitted = JSON.parse(window.localStorage.getItem(MOCK_CHECKINS_KEY) ?? '[]') as StoredMockCheckIn[]
    } catch {
      window.localStorage.removeItem(MOCK_CHECKINS_KEY)
    }
    return [...submitted.map(mapAttendance), ...mockAttendance].slice(0, limit)
  },
}

export const httpDashboardDataService: DashboardDataService = {
  async getActiveSessions() {
    const { data } = await apiClient.get<SessionResponseDto[]>('/sessions/my-sessions', { params: { status: 'active' } })
    return data.map(mapSession)
  },
  async getRecentAttendance(limit = 3) {
    const { data } = await apiClient.get<MyCheckInResponseDto[]>('/checkins/my-checkins', { params: { limit } })
    return data.map(mapAttendance)
  },
}

export const dashboardDataService =
  process.env.NEXT_PUBLIC_USE_MOCK_API === 'false' ? httpDashboardDataService : mockDashboardDataService
