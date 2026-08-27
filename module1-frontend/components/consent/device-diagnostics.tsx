'use client'

import { useEffect, useState } from 'react'
import {
  getStoredDiagnostics,
  queryInitialPermission,
  storeDiagnostic,
  testCameraAccess,
  testLocationAccess,
} from '@/lib/device/permissions'
import type { DeviceDiagnosticResult } from '@/types/consent'

const initialDiagnostic: DeviceDiagnosticResult = {
  state: 'not-requested',
  message: 'Access has not been tested in this tab.',
}

const statusStyles: Record<DeviceDiagnosticResult['state'], string> = {
  granted: 'bg-emerald-100 text-emerald-800',
  denied: 'bg-red-100 text-red-800',
  unavailable: 'bg-amber-100 text-amber-900',
  'insecure-context': 'bg-amber-100 text-amber-900',
  error: 'bg-red-100 text-red-800',
  checking: 'bg-blue-100 text-blue-800',
  prompt: 'bg-blue-100 text-blue-800',
  'not-requested': 'bg-slate-100 text-slate-700',
}

function PermissionCard({
  title,
  description,
  diagnostic,
  onTest,
}: {
  title: string
  description: string
  diagnostic: DeviceDiagnosticResult
  onTest(): void
}) {
  return (
    <article className="card flex flex-col">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <h3 className="font-semibold text-slate-950">{title}</h3>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${statusStyles[diagnostic.state]}`}>
          {diagnostic.state.replaceAll('-', ' ')}
        </span>
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-600">{description}</p>
      <p className="mt-3 flex-1 text-sm font-medium text-slate-800" aria-live="polite">{diagnostic.message}</p>
      <button className="button-secondary mt-5 w-fit" type="button" onClick={onTest} disabled={diagnostic.state === 'checking'}>
        {diagnostic.state === 'checking' ? 'Testing…' : `Test ${title}`}
      </button>
    </article>
  )
}

export function DeviceDiagnostics() {
  const [cameraDiagnostic, setCameraDiagnostic] = useState(initialDiagnostic)
  const [locationDiagnostic, setLocationDiagnostic] = useState(initialDiagnostic)

  useEffect(() => {
    const stored = getStoredDiagnostics()
    const initialise = async () => {
      setCameraDiagnostic(stored.camera ?? await queryInitialPermission('camera'))
      setLocationDiagnostic(stored.location ?? await queryInitialPermission('geolocation'))
    }
    void initialise()
  }, [])

  const testCamera = async () => {
    setCameraDiagnostic({ state: 'checking', message: 'Testing camera access…' })
    const diagnostic = await testCameraAccess()
    setCameraDiagnostic(diagnostic)
    storeDiagnostic('camera', diagnostic)
  }

  const testLocation = async () => {
    setLocationDiagnostic({ state: 'checking', message: 'Testing location access…' })
    const diagnostic = await testLocationAccess()
    setLocationDiagnostic(diagnostic)
    storeDiagnostic('location', diagnostic)
  }

  const fullyReady = cameraDiagnostic.state === 'granted' && locationDiagnostic.state === 'granted'

  return (
    <>
      <div className="grid gap-4 md:grid-cols-2">
        <PermissionCard title="Camera access" description="Confirms that this browser can briefly open a camera. The test stream is closed immediately." diagnostic={cameraDiagnostic} onTest={() => void testCamera()} />
        <PermissionCard title="Location access" description="Confirms that this browser can obtain a current position. Coordinates are not retained by this diagnostic." diagnostic={locationDiagnostic} onTest={() => void testLocation()} />
      </div>
      <div className={`mt-6 rounded-2xl border p-5 ${fullyReady ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`} aria-live="polite">
        <h3 className={`font-semibold ${fullyReady ? 'text-emerald-900' : 'text-amber-950'}`}>{fullyReady ? 'Device tests passed' : 'Device tests incomplete'}</h3>
        <p className={`mt-2 text-sm ${fullyReady ? 'text-emerald-800' : 'text-amber-900'}`}>{fullyReady ? 'Camera and location were available during their latest tests.' : 'Test both features to diagnose this device. Access will still be confirmed during every check-in.'}</p>
      </div>
    </>
  )
}
