'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { GuestOnlyRoute } from '@/components/guest-only-route'
import { authService } from '@/lib/api/auth-service'
import { getApiErrorMessage } from '@/lib/api/client'
import { isValidEmail, normalizeEmail } from '@/lib/auth/validation'

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isComplete, setIsComplete] = useState(false)

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

    setIsSubmitting(true)
    try {
      await authService.requestPasswordReset(normalizedEmail)
      setIsComplete(true)
    } catch (requestError) {
      setError(getApiErrorMessage(requestError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <GuestOnlyRoute>
      <AppShell>
        <div className="mx-auto max-w-lg py-8">
          <p className="eyebrow">Account recovery</p>
          <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-950">Reset your password</h1>
          {isComplete ? (
            <section className="card mt-8">
              <h2 className="text-lg font-semibold text-slate-950">Check your email</h2>
              <p className="mt-3 leading-7 text-slate-600">If an account exists for this email, password-reset instructions have been sent.</p>
              <p className="mt-3 text-sm text-blue-800">Mock mode does not send an actual email or create a reset token.</p>
              <Link className="button-primary mt-6" href="/login">Return to login</Link>
            </section>
          ) : (
            <form className="card mt-8" onSubmit={handleSubmit} noValidate>
              <p className="mb-5 text-sm leading-6 text-slate-600">Enter your account email. For privacy, SAIV shows the same response whether or not an account exists.</p>
              <label className="form-label" htmlFor="recovery-email">Email address</label>
              <input className="form-input" id="recovery-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} />
              {error && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</div>}
              <button className="button-primary mt-6 w-full" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Requesting…' : 'Request reset instructions'}</button>
              <p className="mt-5 text-center text-sm"><Link className="font-semibold text-blue-700 hover:text-blue-900" href="/login">Back to login</Link></p>
            </form>
          )}
        </div>
      </AppShell>
    </GuestOnlyRoute>
  )
}
