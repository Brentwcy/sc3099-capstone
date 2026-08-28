export type SessionAvailability = 'open' | 'upcoming' | 'checked-in' | 'closed'
export type AttendanceStatus = 'approved' | 'pending-review' | 'rejected'

export interface DashboardSession {
  id: string
  courseCode: string
  courseName: string
  instructor: string
  sessionName: string
  location: string
  startsAt: string
  endsAt: string
  availability: SessionAvailability
  checkedInAt?: string
}

export interface AttendanceRecord {
  id: string
  courseCode: string
  courseName: string
  instructor: string
  occurredAt: string
  sessionType: string
  status: AttendanceStatus
}

export interface DashboardDataService {
  getActiveSessions(): Promise<DashboardSession[]>
  getRecentAttendance(limit?: number): Promise<AttendanceRecord[]>
}
