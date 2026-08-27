'use client'

import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { ConsentControls } from '@/components/consent/consent-controls'
import { OnboardingProgress } from '@/components/onboarding-progress'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'

export default function OnboardingConsentPage() {
  const { user } = useAuth()
  const consentComplete = Boolean(user?.camera_consent && user.geolocation_consent)

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="mx-auto max-w-4xl">
          <OnboardingProgress currentStep={2} />
          <section className="mt-8 max-w-3xl">
            <p className="eyebrow">Account setup</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Review privacy and consent</h1>
            <p className="mt-3 leading-7 text-slate-600">SAIV needs account-level consent before it can process camera or location evidence. This step does not open your camera or request your location.</p>
          </section>

          <section className="card mt-8 border-blue-200 bg-blue-50">
            <h2 className="font-semibold text-blue-950">What happens during attendance</h2>
            <p className="mt-2 text-sm leading-6 text-blue-900">After you explicitly start a check-in, SAIV requests current camera and location access. Face images may be transmitted for verification but are not retained in the primary database. Location is collected only for attendance verification.</p>
          </section>

          <section className="mt-8">
            <ConsentControls />
          </section>

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <Link className="text-center text-sm font-semibold text-slate-600 hover:text-slate-950" href="/dashboard">Finish setup later</Link>
            {consentComplete ? (
              <Link className="button-primary" href="/onboarding/face-enrollment">Continue to face enrollment</Link>
            ) : (
              <span className="text-sm font-medium text-amber-800">Enable both consent options to continue.</span>
            )}
          </div>
        </div>
      </AppShell>
    </ProtectedRoute>
  )
}
