'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AppShell } from '@/components/app-shell'
import { GuestOnlyRoute } from '@/components/guest-only-route'
import { PasswordInput } from '@/components/password-input'
import { PasswordRequirements } from '@/components/password-requirements'
import { useAuth } from '@/contexts/auth-context'
import { getApiErrorMessage } from '@/lib/api/client'
import { getPasswordError, isValidEmail, normalizeEmail } from '@/lib/auth/validation'

export default function RegisterPage() {
  const router = useRouter()
  const { register } = useAuth()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError('')

    const normalizedName = fullName.trim()
    const normalizedEmail = normalizeEmail(email)

    if (!normalizedName) {
      setError('Full name is required.')
      return
    }

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

    if (!confirmPassword) {
      setError('Confirm password is required.')
      return
    }

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setIsSubmitting(true)
    try {
      await register({ full_name: normalizedName, email: normalizedEmail, password, role: 'student' })
      router.push('/onboarding/consent')
    } catch (registrationError) {
      setError(getApiErrorMessage(registrationError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <GuestOnlyRoute>
      <AppShell>
      <div className="mx-auto max-w-lg py-8">
        <p className="eyebrow">Student registration</p>
        <h1 className="mt-3 text-4xl font-bold tracking-tight text-slate-950">Create your account</h1>
        <p className="mt-3 text-slate-600">Registration currently uses the API-compatible mock service.</p>
        <form className="card mt-8" onSubmit={handleSubmit} noValidate>
          <label className="form-label" htmlFor="full-name">Full name</label>
          <input className="form-input" id="full-name" autoComplete="name" required value={fullName} onChange={(event) => setFullName(event.target.value)} />
          <label className="form-label mt-5" htmlFor="email">Email address</label>
          <input className="form-input" id="email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          <label className="form-label mt-5" htmlFor="password">Password</label>
          <PasswordInput className="form-input" id="password" autoComplete="new-password" minLength={8} required value={password} onChange={(event) => setPassword(event.target.value)} />
          <PasswordRequirements password={password} />
          <label className="form-label mt-5" htmlFor="confirm-password">Confirm password</label>
          <PasswordInput className="form-input" id="confirm-password" autoComplete="new-password" minLength={8} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
          {error && <div className="mt-5 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800" role="alert">{error}</div>}
          <button className="button-primary mt-6 w-full" type="submit" disabled={isSubmitting}>{isSubmitting ? 'Creating account…' : 'Create account'}</button>
          <p className="mt-5 text-center text-sm text-slate-600">Already registered? <Link className="font-semibold text-blue-700 hover:text-blue-900" href="/login">Sign in</Link></p>
        </form>
      </div>
      </AppShell>
    </GuestOnlyRoute>
  )
}
