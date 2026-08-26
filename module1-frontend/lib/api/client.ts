import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { clearSession, getSession, setSession } from '@/lib/auth/session-storage'
import type { ApiErrorBody, AuthTokens } from '@/types/auth'

const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${backendUrl.replace(/\/$/, '')}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

interface RetryableRequest extends InternalAxiosRequestConfig {
  _authRetry?: boolean
}

let refreshRequest: Promise<AuthTokens> | null = null

apiClient.interceptors.request.use((config) => {
  const accessToken = getSession()?.accessToken
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const request = error.config as RetryableRequest | undefined
    const session = getSession()
    const isAuthRequest = request?.url?.startsWith('/auth/') ?? false

    if (error.response?.status !== 401 || !request || request._authRetry || isAuthRequest || !session) {
      return Promise.reject(error)
    }

    request._authRetry = true

    try {
      refreshRequest ??= axios
        .post<AuthTokens>(`${apiClient.defaults.baseURL}/auth/refresh`, {
          refresh_token: session.refreshToken,
        })
        .then(({ data }) => data)
        .finally(() => {
          refreshRequest = null
        })

      const tokens = await refreshRequest
      setSession({
        ...session,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      })
      request.headers.Authorization = `Bearer ${tokens.access_token}`
      return apiClient(request)
    } catch (refreshError) {
      clearSession()
      return Promise.reject(refreshError)
    }
  },
)

export function getApiErrorMessage(error: unknown): string {
  if (!axios.isAxiosError<ApiErrorBody>(error)) {
    return error instanceof Error ? error.message : 'Something went wrong. Please try again.'
  }

  const axiosError = error as AxiosError<ApiErrorBody>
  const detail = axiosError.response?.data?.detail

  if (typeof detail === 'string') return detail

  if (Array.isArray(detail)) {
    const messages = detail.flatMap((item) => (item.msg ? [item.msg] : []))
    if (messages.length > 0) return messages.join(', ')
  }

  if (axiosError.code === 'ECONNABORTED') return 'The request timed out. Please try again.'
  if (!axiosError.response) return 'Unable to reach the attendance service.'
  return `Request failed (${axiosError.response.status}). Please try again.`
}
