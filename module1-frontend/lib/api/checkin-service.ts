import { apiClient } from '@/lib/api/client'
import type { CheckInRequest, CheckInResult, StoredMockCheckIn } from '@/types/checkin'

export const MOCK_CHECKINS_KEY = 'saiv.mock.checkins'

export interface CheckInService {
  submit(payload: CheckInRequest, context: { courseCode: string; sessionName: string }): Promise<CheckInResult>
}

function readMockCheckIns(): StoredMockCheckIn[] {
  try {
    return JSON.parse(window.localStorage.getItem(MOCK_CHECKINS_KEY) ?? '[]') as StoredMockCheckIn[]
  } catch {
    return []
  }
}

export const mockCheckInService: CheckInService = {
  async submit(payload, context) {
    await new Promise((resolve) => window.setTimeout(resolve, 900))
    const existing = readMockCheckIns().find((record) => record.session_id === payload.session_id)
    if (existing) throw new Error('You have already checked in to this session.')

    const result: StoredMockCheckIn = {
      id: crypto.randomUUID(), session_id: payload.session_id,
      session_name: context.sessionName, course_code: context.courseCode,
      status: 'approved', checked_in_at: new Date().toISOString(), risk_score: 0.12,
    }
    window.localStorage.setItem(MOCK_CHECKINS_KEY, JSON.stringify([result, ...readMockCheckIns()]))
    return result
  },
}

export const httpCheckInService: CheckInService = {
  async submit(payload) {
    const { data } = await apiClient.post<CheckInResult>('/checkins/', payload)
    return data
  },
}

export const checkInService = process.env.NEXT_PUBLIC_USE_MOCK_API === 'false'
  ? httpCheckInService : mockCheckInService
