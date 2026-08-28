import { apiClient } from '@/lib/api/client'
import { getSession } from '@/lib/auth/session-storage'
import type { AuthTokens, LoginRequest, LoginResponse, RegisterRequest, User } from '@/types/auth'

export interface AuthService {
  login(credentials: LoginRequest): Promise<LoginResponse>
  register(details: RegisterRequest): Promise<User>
  refresh(refreshToken: string): Promise<AuthTokens>
  getCurrentUser(accessToken: string): Promise<User>
  requestPasswordReset(email: string): Promise<void>
}

const wait = (milliseconds: number) =>
  new Promise((resolve) => window.setTimeout(resolve, milliseconds))

const mockUser = (email: string): User => ({
  id: 'student-1',
  email,
  full_name: 'Brent Wong',
  role: 'student',
  is_active: true,
  camera_consent: false,
  geolocation_consent: false,
  face_enrolled: false,
  created_at: new Date().toISOString(),
})

let registeredMockUser: User | null = null

export const mockAuthService: AuthService = {
  async login({ email, password }) {
    await wait(450)
    if (password.length < 8) throw new Error('Password must contain at least 8 characters.')

    return {
      access_token: 'mock-access-token',
      refresh_token: 'mock-refresh-token',
      token_type: 'bearer',
      user: registeredMockUser?.email === email ? registeredMockUser : mockUser(email),
    }
  },

  async register(details) {
    await wait(450)
    registeredMockUser = {
      ...mockUser(details.email),
      full_name: details.full_name,
      role: details.role,
    }
    return registeredMockUser
  },

  async refresh() {
    await wait(250)
    return {
      access_token: 'mock-access-token-refreshed',
      refresh_token: 'mock-refresh-token-refreshed',
      token_type: 'bearer',
    }
  },

  async getCurrentUser() {
    await wait(250)
    const user = getSession()?.user
    if (!user) throw new Error('Your session has expired. Please sign in again.')
    return user
  },
  async requestPasswordReset() {
    await wait(400)
  },
}

export const httpAuthService: AuthService = {
  async login(credentials) {
    const { data } = await apiClient.post<LoginResponse>('/auth/login', credentials)
    return data
  },

  async register(details) {
    const { data } = await apiClient.post<User>('/auth/register', details)
    return data
  },

  async refresh(refreshToken) {
    const { data } = await apiClient.post<AuthTokens>('/auth/refresh', {
      refresh_token: refreshToken,
    })
    return data
  },

  async getCurrentUser(accessToken) {
    const { data } = await apiClient.get<User>('/users/me', {
      headers: { Authorization: `Bearer ${accessToken}` },
    })
    return data
  },
  async requestPasswordReset(email) {
    await apiClient.post('/auth/forgot-password', { email })
  },
}

export const authService =
  process.env.NEXT_PUBLIC_USE_MOCK_API === 'false' ? httpAuthService : mockAuthService
