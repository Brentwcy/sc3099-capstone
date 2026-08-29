export type SessionAvailability = 'open' | 'upcoming' | 'closed'
export type AttendanceStatus = 'pending' | 'approved' | 'flagged' | 'rejected' | 'appealed'

export interface DashboardSession {
  id: string
  courseCode: string | null
  courseName: string | null
  sessionName: string
  sessionType: 'lecture' | 'tutorial' | 'lab' | 'exam'
  venueName: string | null
  startsAt: string
  endsAt: string
  checkinClosesAt: string
  requireLivenessCheck: boolean
  requireFaceMatch: boolean
  qrCodeEnabled: boolean
  availability: SessionAvailability
}

export interface AttendanceRecord {
  id: string
  sessionId: string
  courseCode: string
  sessionName: string
  checkedInAt: string
  status: AttendanceStatus
  riskScore: number
}

export interface DashboardDataService {
  getActiveSessions(): Promise<DashboardSession[]>
  getRecentAttendance(limit?: number): Promise<AttendanceRecord[]>
}
