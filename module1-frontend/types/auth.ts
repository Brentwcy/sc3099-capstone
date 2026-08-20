export type UserRole = 'student' | 'ta' | 'instructor' | 'admin'

export interface User {
  id: string
  email: string
  full_name: string
  role: UserRole
  is_active: boolean
  camera_consent?: boolean
  geolocation_consent?: boolean
  face_enrolled?: boolean
  created_at?: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface RegisterRequest extends LoginRequest {
  full_name: string
  role: UserRole
}

export interface AuthTokens {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
}

export interface LoginResponse extends AuthTokens {
  user: User
}

export interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>
}
