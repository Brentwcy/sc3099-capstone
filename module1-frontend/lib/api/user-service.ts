import { apiClient } from '@/lib/api/client'
import { getSession } from '@/lib/auth/session-storage'
import type { UpdateConsentRequest } from '@/types/consent'
import type { User } from '@/types/auth'
import type { UpdateProfileRequest } from '@/types/settings'

export interface UserService {
  updateConsent(consent: UpdateConsentRequest): Promise<User>
  updateProfile(profile: UpdateProfileRequest): Promise<User>
  enrollFace(image: string): Promise<User>
}

export const mockUserService: UserService = {
  async updateConsent(consent) {
    await new Promise((resolve) => window.setTimeout(resolve, 300))
    const user = getSession()?.user
    if (!user) throw new Error('Your session has expired. Please sign in again.')
    return { ...user, ...consent }
  },
  async updateProfile(profile) {
    await new Promise((resolve) => window.setTimeout(resolve, 300))
    const user = getSession()?.user
    if (!user) throw new Error('Your session has expired. Please sign in again.')
    return { ...user, full_name: profile.full_name }
  },
  async enrollFace() {
    await new Promise((resolve) => window.setTimeout(resolve, 500))
    const user = getSession()?.user
    if (!user) throw new Error('Your session has expired. Please sign in again.')
    return { ...user, face_enrolled: true }
  },
}

export const httpUserService: UserService = {
  async updateConsent(consent) {
    const { data } = await apiClient.put<User>('/users/me', consent)
    return data
  },
  async updateProfile(profile) {
    const { data } = await apiClient.put<User>('/users/me', profile)
    return data
  },
  async enrollFace(image) {
    const { data } = await apiClient.post<User>('/users/me/face-enrollment', { image })
    return data
  },
}

export const userService =
  process.env.NEXT_PUBLIC_USE_MOCK_API === 'false' ? httpUserService : mockUserService
