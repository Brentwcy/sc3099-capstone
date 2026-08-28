'use client'

import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { OnboardingProgress } from '@/components/onboarding-progress'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'

export default function FaceEnrollmentPage() {
  const { user } = useAuth()
  const consentComplete = Boolean(user?.camera_consent && user.geolocation_consent)

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="mx-auto max-w-4xl">
          <OnboardingProgress currentStep={3} completedSteps={consentComplete ? 2 : 1} />
          <section className="card mt-8">
            <p className="eyebrow">Account setup</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Face enrollment is not available yet</h1>
            <p className="mt-3 max-w-2xl leading-7 text-slate-600">You can return to your dashboard and complete face enrollment later. Attendance check-in will remain unavailable until enrollment is complete.</p>
            {!consentComplete && (
              <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Camera and location consent must be completed before face enrollment. <Link className="font-semibold underline" href="/onboarding/consent">Review consent</Link>.</div>
            )}
            <div className="mt-6 flex flex-wrap gap-3">
              <Link className="button-primary" href="/dashboard">Finish setup later</Link>
              <Link className="button-secondary" href="/onboarding/consent">Back to consent</Link>
            </div>
          </section>
        </div>
      </AppShell>
    </ProtectedRoute>
  )
}
