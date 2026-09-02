'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { ConsentControls } from '@/components/consent/consent-controls'
import { DeviceDiagnostics } from '@/components/consent/device-diagnostics'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'
import { getApiErrorMessage } from '@/lib/api/client'

type FormMessage = { text: string; type: 'success' | 'error' }

export default function SettingsPage() {
  const { user, updateProfile } = useAuth()
  const [isEditingProfile, setIsEditingProfile] = useState(false)
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [profileMessage, setProfileMessage] = useState<FormMessage | null>(null)
  const [isSavingProfile, setIsSavingProfile] = useState(false)

  const saveProfile = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const normalizedName = fullName.trim()
    if (!normalizedName) {
      setProfileMessage({ text: 'Full name is required.', type: 'error' })
      return
    }

    setProfileMessage(null)
    setIsSavingProfile(true)
    try {
      await updateProfile({ full_name: normalizedName })
      setProfileMessage({ text: 'Profile updated.', type: 'success' })
      setIsEditingProfile(false)
    } catch (error) {
      setProfileMessage({ text: getApiErrorMessage(error), type: 'error' })
    } finally {
      setIsSavingProfile(false)
    }
  }

  return (
    <ProtectedRoute>
      <AppShell>
        <section className="max-w-3xl">
          <p className="eyebrow">Settings</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Manage your account</h1>
          <p className="mt-3 leading-7 text-slate-600">Update your profile, review identity and privacy choices, or diagnose device access.</p>
        </section>

        <section className="card mt-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div><h2 className="text-xl font-semibold text-slate-950">Account</h2><p className="mt-1 text-sm text-slate-600">Your student profile and account status.</p></div>
            {!isEditingProfile && <button className="button-secondary" type="button" onClick={() => { setFullName(user?.full_name ?? ''); setProfileMessage(null); setIsEditingProfile(true) }}>Edit profile</button>}
          </div>

          {isEditingProfile ? (
            <form className="mt-6 max-w-xl" onSubmit={saveProfile} noValidate>
              <label className="form-label" htmlFor="settings-full-name">Full name</label>
              <input className="form-input" id="settings-full-name" autoComplete="name" value={fullName} onChange={(event) => setFullName(event.target.value)} />
              <div className="mt-5 flex flex-wrap gap-3">
                <button className="button-primary" type="submit" disabled={isSavingProfile}>{isSavingProfile ? 'Saving…' : 'Save profile'}</button>
                <button className="button-secondary" type="button" disabled={isSavingProfile} onClick={() => { setIsEditingProfile(false); setFullName(user?.full_name ?? ''); setProfileMessage(null) }}>Cancel</button>
              </div>
            </form>
          ) : (
            <dl className="mt-6 grid gap-5 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div><dt className="text-slate-500">Full name</dt><dd className="mt-1 font-medium text-slate-950">{user?.full_name}</dd></div>
              <div><dt className="text-slate-500">Email</dt><dd className="mt-1 break-all font-medium text-slate-950">{user?.email}</dd></div>
              <div><dt className="text-slate-500">Role</dt><dd className="mt-1 font-medium capitalize text-slate-950">{user?.role}</dd></div>
              <div><dt className="text-slate-500">Status</dt><dd className="mt-1 font-medium text-slate-950">{user?.is_active ? 'Active' : 'Inactive'}</dd></div>
            </dl>
          )}
          {profileMessage && <p className={`mt-4 text-sm ${profileMessage.type === 'success' ? 'text-emerald-700' : 'text-red-700'}`} aria-live="polite">{profileMessage.text}</p>}
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold text-slate-950">Identity and privacy</h2>
          <p className="mt-2 text-sm text-slate-600">Manage face enrollment and account-level consent for attendance verification.</p>
          <div className="card mt-4 flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
            <div><h3 className="font-semibold text-slate-950">Face enrollment</h3><p className="mt-2 text-sm text-slate-600">Status: <span className="font-medium">{user?.face_enrolled ? 'Enrolled' : 'Not enrolled'}</span></p></div>
            <Link className="button-secondary shrink-0" href="/onboarding/face-enrollment">{user?.face_enrolled ? 'Manage enrollment' : 'Enroll face'}</Link>
          </div>
          <div className="mt-4"><ConsentControls /></div>
        </section>

        <section className="mt-8">
          <h2 className="text-xl font-semibold text-slate-950">Device checks</h2>
          <p className="mt-2 text-sm text-slate-600">Test this browser without permanently treating the result as check-in authorization.</p>
          <div className="mt-4"><DeviceDiagnostics /></div>
        </section>
      </AppShell>
    </ProtectedRoute>
  )
}
