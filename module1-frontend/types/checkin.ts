import type { AttendanceStatus } from '@/types/dashboard'

export interface CheckInRequest {
  session_id: string
  latitude: number
  longitude: number
  location_accuracy_meters: number
  device_fingerprint: string
  liveness_challenge_response?: string
  qr_code?: string
}

export interface CheckInResult {
  id: string
  session_id: string
  status: AttendanceStatus
  checked_in_at: string
  risk_score: number
}

export interface StoredMockCheckIn extends CheckInResult {
  session_name: string
  course_code: string
}
