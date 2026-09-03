'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { GuestOnlyRoute } from '@/components/guest-only-route'
import { PasswordInput } from '@/components/password-input'
import { useAuth } from '@/contexts/auth-context'
import { getApiErrorMessage } from '@/lib/api/client'
import { getPasswordError, isValidEmail, normalizeEmail } from '@/lib/auth/validation'

export default function LoginPage() {
  const router = useRouter()
  const { login } = useAuth()
  const [email, setEmail] = useState('student@ntu.edu.sg')
  const [password, setPassword] = useState('password123')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')

    const normalizedEmail = normalizeEmail(email)
    if (!normalizedEmail) {
      setError('Email address is required.')
      return
    }
    if (!isValidEmail(normalizedEmail)) {
      setError('Enter a valid email address.')
      return
    }
    const passwordError = getPasswordError(password)
    if (passwordError) {
      setError(passwordError)
      return
    }

    setIsSubmitting(true)

    try {
      await login({ email: normalizedEmail, password })
      router.push('/dashboard')
    } catch (loginError) {
      setError(getApiErrorMessage(loginError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <GuestOnlyRoute>
      <AppShell>
      <div className="mx-auto grid max-w-4xl gap-8 py-8 lg:grid-cols-2 lg:items-center">
        <section>
          <p className="eyebrow">Student access</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-950">Welcome back</h1>
          <p className="mt-4 leading-7 text-slate-600">
            Sign in to view active sessions and begin a secure attendance check-in.
          </p>
        </section>

        <form className="card" onSubmit={handleSubmit} noValidate>
          <div>
            <label className="form-label" htmlFor="email">Email address</label>
            <input
              className="form-input"
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>

          <div className="mt-5">
            <label className="form-label" htmlFor="password">Password</label>
            <PasswordInput
              className="form-input"
              id="password"
              name="password"
              autoComplete="current-password"
              minLength={8}
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>

          {error && (
            <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">
              {error}
            </div>
          )}

          <button className="button-primary mt-6 w-full" type="submit" disabled={isSubmitting}>
            {isSubmitting ? 'Signing in…' : 'Sign in'}
          </button>

          <p className="mt-5 text-center text-sm text-slate-600">
            Need an account?{' '}
            <Link className="font-semibold text-blue-700 hover:text-blue-900" href="/register">Register</Link>
          </p>
        </form>
      </div>
      </AppShell>
    </GuestOnlyRoute>
  )
}
