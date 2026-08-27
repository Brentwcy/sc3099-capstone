'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { FeaturePlaceholder } from '@/components/feature-placeholder'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'
import { getStoredDiagnostics } from '@/lib/device/permissions'
import type { StoredDeviceDiagnostics } from '@/types/consent'

export default function SessionsPage() {
  const { user } = useAuth()
  const [diagnostics, setDiagnostics] = useState<StoredDeviceDiagnostics>({})

  useEffect(() => setDiagnostics(getStoredDiagnostics()), [])

  const missingCameraConsent = !user?.camera_consent
  const missingLocationConsent = !user?.geolocation_consent
  const hasRequiredConsent = !missingCameraConsent && !missingLocationConsent
  const diagnosticsPassed = diagnostics.camera?.state === 'granted' && diagnostics.location?.state === 'granted'

  return (
    <ProtectedRoute>
      <AppShell>
        {!hasRequiredConsent ? (
          <section className="mx-auto max-w-2xl rounded-2xl border border-amber-200 bg-amber-50 p-6">
            <p className="eyebrow">Check-in prerequisites</p>
            <h1 className="mt-2 text-2xl font-bold text-amber-950">Consent setup is required</h1>
            <p className="mt-3 text-sm leading-6 text-amber-900">SAIV cannot begin a check-in until you grant the required account consent. No hardware access has been requested.</p>
            <ul className="mt-5 space-y-2 text-sm text-amber-950">
              <li>{missingCameraConsent ? '○' : '✓'} Camera consent</li>
              <li>{missingLocationConsent ? '○' : '✓'} Location consent</li>
            </ul>
            <Link className="button-primary mt-6" href="/settings">Configure consent and permissions</Link>
          </section>
        ) : (
          <>
            {!diagnosticsPassed && (
              <section className="mb-6 rounded-xl border border-blue-200 bg-blue-50 p-4 text-sm text-blue-900">
                Your consent is ready, but one or more device checks have not recently passed. You can <Link className="font-semibold underline" href="/settings">test access now</Link>; the final check-in flow will confirm access again.
              </section>
            )}
            <FeaturePlaceholder title="Sessions" description="Consent requirements are satisfied. Active-session discovery, liveness prompts, location capture, and attendance submission will be built in the next milestone." />
          </>
        )}
      </AppShell>
    </ProtectedRoute>
  )
}
