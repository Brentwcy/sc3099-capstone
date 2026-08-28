'use client'

import Link from 'next/link'
import { FormEvent, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { ConsentControls } from '@/components/consent/consent-controls'
import { DeviceDiagnostics } from '@/components/consent/device-diagnostics'
import { ProtectedRoute } from '@/components/protected-route'
import { PasswordInput } from '@/components/password-input'
import { PasswordRequirements } from '@/components/password-requirements'
import { useAuth } from '@/contexts/auth-context'
import { getApiErrorMessage } from '@/lib/api/client'
import { getPasswordError } from '@/lib/auth/validation'

type FormMessage = { text: string; type: 'success' | 'error' }

export default function SettingsPage() {
  const { user, updateProfile, changePassword } = useAuth()
  const [isEditingProfile, setIsEditingProfile] = useState(false)
  const [fullName, setFullName] = useState(user?.full_name ?? '')
  const [profileMessage, setProfileMessage] = useState<FormMessage | null>(null)
  const [isSavingProfile, setIsSavingProfile] = useState(false)
  const [isChangingPassword, setIsChangingPassword] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordMessage, setPasswordMessage] = useState<FormMessage | null>(null)
  const [isSavingPassword, setIsSavingPassword] = useState(false)

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

  const savePassword = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setPasswordMessage(null)

    if (!currentPassword) {
      setPasswordMessage({ text: 'Current password is required.', type: 'error' })
      return
    }
    const newPasswordError = getPasswordError(newPassword, 'New password')
    if (newPasswordError) {
      setPasswordMessage({ text: newPasswordError, type: 'error' })
      return
    }
    if (newPassword === currentPassword) {
      setPasswordMessage({ text: 'New password must be different from your current password.', type: 'error' })
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordMessage({ text: 'New passwords do not match.', type: 'error' })
      return
    }

    setIsSavingPassword(true)
    try {
      const response = await changePassword({ current_password: currentPassword, new_password: newPassword })
      setPasswordMessage({ text: response.message, type: 'success' })
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setIsChangingPassword(false)
    } catch (error) {
      setPasswordMessage({ text: getApiErrorMessage(error), type: 'error' })
    } finally {
      setIsSavingPassword(false)
    }
  }

  return (
    <ProtectedRoute>
      <AppShell>
        <section className="max-w-3xl">
          <p className="eyebrow">Settings</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Manage your account</h1>
          <p className="mt-3 leading-7 text-slate-600">Update your profile and security details, review identity and privacy choices, or diagnose device access.</p>
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

        <section className="card mt-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div><div className="flex flex-wrap items-center gap-2"><h2 className="text-xl font-semibold text-slate-950">Security</h2><span className="rounded-full bg-blue-100 px-2.5 py-1 text-xs font-semibold text-blue-800">Mock mode</span></div><p className="mt-1 text-sm text-slate-600">Change the password used to access your account.</p></div>
            {!isChangingPassword && <button className="button-secondary" type="button" onClick={() => { setPasswordMessage(null); setIsChangingPassword(true) }}>Change password</button>}
          </div>

          {isChangingPassword && (
            <form className="mt-6 max-w-xl" onSubmit={savePassword} noValidate>
              <label className="form-label" htmlFor="current-password">Current password</label>
              <PasswordInput className="form-input" id="current-password" autoComplete="current-password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
              <label className="form-label mt-5" htmlFor="new-password">New password</label>
              <PasswordInput className="form-input" id="new-password" autoComplete="new-password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
              <PasswordRequirements password={newPassword} />
              <label className="form-label mt-5" htmlFor="confirm-password">Confirm new password</label>
              <PasswordInput className="form-input" id="confirm-password" autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
              <div className="mt-5 flex flex-wrap gap-3">
                <button className="button-primary" type="submit" disabled={isSavingPassword}>{isSavingPassword ? 'Updating…' : 'Update password'}</button>
                <button className="button-secondary" type="button" disabled={isSavingPassword} onClick={() => { setIsChangingPassword(false); setCurrentPassword(''); setNewPassword(''); setConfirmPassword(''); setPasswordMessage(null) }}>Cancel</button>
              </div>
            </form>
          )}
          {passwordMessage && <p className={`mt-4 text-sm ${passwordMessage.type === 'success' ? 'text-emerald-700' : 'text-red-700'}`} aria-live="polite">{passwordMessage.text}</p>}
          <p className="mt-4 text-xs text-slate-500">Password updates currently run in mock mode. Real verification requires the Module 2 password endpoint.</p>
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
