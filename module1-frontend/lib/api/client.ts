import axios, { AxiosError } from 'axios'
import type { ApiErrorBody } from '@/types/auth'

const backendUrl = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${backendUrl.replace(/\/$/, '')}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
  timeout: 15_000,
})

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
