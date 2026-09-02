'use client'

import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import { Suspense, useEffect, useRef, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'
import { checkInService } from '@/lib/api/checkin-service'
import { getApiErrorMessage } from '@/lib/api/client'
import { dashboardDataService } from '@/lib/api/dashboard-data-service'
import { getDeviceFingerprint } from '@/lib/device/fingerprint'
import type { CheckInResult } from '@/types/checkin'
import type { DashboardSession } from '@/types/dashboard'

type Step = 'review' | 'location' | 'camera' | 'ready' | 'submitting' | 'complete'
type Position = { latitude: number; longitude: number; accuracy: number }

const stepLabels = ['Review', 'Location', 'Verification', 'Submit']
const stepNumber: Record<Step, number> = { review: 1, location: 2, camera: 3, ready: 4, submitting: 4, complete: 4 }
const isMockMode = process.env.NEXT_PUBLIC_USE_MOCK_API !== 'false'
const formatDateTime = (value: string) => new Intl.DateTimeFormat('en-SG', {
  day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit',
}).format(new Date(value))

function CheckInFlow() {
  const sessionId = useSearchParams().get('session')
  const { user } = useAuth()
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [session, setSession] = useState<DashboardSession | null>(null)
  const [step, setStep] = useState<Step>('review')
  const [position, setPosition] = useState<Position | null>(null)
  const [result, setResult] = useState<CheckInResult | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [cameraActive, setCameraActive] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    dashboardDataService.getActiveSessions()
      .then((sessions) => { if (active) setSession(sessions.find((item) => item.id === sessionId) ?? null) })
      .catch(() => { if (active) setError('This session could not be loaded.') })
      .finally(() => { if (active) setIsLoading(false) })
    return () => { active = false; streamRef.current?.getTracks().forEach((track) => track.stop()) }
  }, [sessionId])

  const captureLocation = () => {
    setError('')
    setStep('location')
    if (!navigator.geolocation) {
      setError('Location is not supported by this browser.')
      return
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        setPosition({ latitude: coords.latitude, longitude: coords.longitude, accuracy: coords.accuracy })
        setStep('camera')
      },
      (locationError) => setError(locationError.code === locationError.PERMISSION_DENIED
        ? 'Location access was denied. Enable it in your browser settings and try again.'
        : 'Your location could not be determined. Move to an open area and try again.'),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
    )
  }

  const useDemoLocation = () => {
    setPosition({ latitude: 1.3483, longitude: 103.6831, accuracy: 10 })
    setError('')
    setStep('camera')
  }

  const startVerification = async () => {
    setError('')
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Camera access is not supported by this browser.')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' }, audio: false })
      streamRef.current = stream
      if (videoRef.current) videoRef.current.srcObject = stream
      setCameraActive(true)
    } catch {
      setError('Camera access was denied or the camera is unavailable.')
    }
  }

  const completeVerification = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setCameraActive(false)
    setStep('ready')
  }

  const submit = async () => {
    if (!session || !position) return
    setError('')
    setStep('submitting')
    try {
      const response = await checkInService.submit({
        session_id: session.id,
        latitude: position.latitude,
        longitude: position.longitude,
        location_accuracy_meters: position.accuracy,
        device_fingerprint: getDeviceFingerprint(),
        liveness_challenge_response: session.requireLivenessCheck ? 'mock_camera_challenge_passed' : undefined,
      }, { courseCode: session.courseCode ?? 'Unknown course', sessionName: session.sessionName })
      setResult(response)
      setStep('complete')
    } catch (submitError) {
      setError(getApiErrorMessage(submitError))
      setStep('ready')
    }
  }

  const consentComplete = Boolean(user?.camera_consent && user?.geolocation_consent)
  const setupComplete = consentComplete && Boolean(user?.face_enrolled)

  return (
    <ProtectedRoute><AppShell><div className="mx-auto max-w-3xl">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><p className="eyebrow">Attendance check-in</p><h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Verify your attendance</h1></div>
        <Link className="button-secondary" href="/sessions">Back to sessions</Link>
      </div>

      <ol className="mt-8 grid grid-cols-4 gap-2" aria-label="Check-in progress">
        {stepLabels.map((label, index) => {
          const number = index + 1
          return <li key={label} className={`rounded-lg px-2 py-3 text-center text-xs font-semibold sm:text-sm ${number <= stepNumber[step] ? 'bg-blue-700 text-white' : 'bg-slate-100 text-slate-500'}`}>{number}. {label}</li>
        })}
      </ol>

      {isLoading ? <div className="card mt-6 text-sm text-slate-500">Loading session…</div> : !session ? (
        <section className="card mt-6"><h2 className="text-xl font-semibold text-slate-950">Session unavailable</h2><p className="mt-2 text-slate-600">This session may have closed or the link may be invalid.</p><Link className="button-primary mt-6" href="/sessions">View available sessions</Link></section>
      ) : !setupComplete ? (
        <section className="card mt-6"><h2 className="text-xl font-semibold text-slate-950">Complete setup first</h2><p className="mt-2 text-slate-600">Camera and location consent plus face enrollment are required before check-in.</p><Link className="button-primary mt-6" href={consentComplete ? '/onboarding/face-enrollment' : '/onboarding/consent'}>Complete setup</Link></section>
      ) : step === 'complete' && result ? (
        <section className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-8 text-center">
          <div className="mx-auto grid h-14 w-14 place-items-center rounded-full bg-emerald-600 text-2xl font-bold text-white">✓</div>
          <h2 className="mt-5 text-2xl font-bold capitalize text-emerald-950">Attendance {result.status}</h2>
          <p className="mt-2 text-emerald-900">Your check-in for {session.sessionName} was submitted at {formatDateTime(result.checked_in_at)}.</p>
          <div className="mt-6 flex flex-wrap justify-center gap-3"><Link className="button-primary" href="/history">View history</Link><Link className="button-secondary" href="/dashboard">Return to dashboard</Link></div>
        </section>
      ) : (
        <section className="card mt-6">
          <div className="border-b border-slate-200 pb-5"><p className="text-sm font-semibold text-blue-700">{[session.courseCode, session.courseName].filter(Boolean).join(' ')}</p><h2 className="mt-1 text-xl font-semibold text-slate-950">{session.sessionName}</h2><p className="mt-1 text-sm text-slate-600">{session.venueName ?? 'Venue not specified'} · closes {formatDateTime(session.checkinClosesAt)}</p></div>

          {step === 'review' && <div className="mt-6"><h3 className="font-semibold text-slate-950">Before you begin</h3><ul className="mt-3 space-y-2 text-sm leading-6 text-slate-600"><li>• Stay at the class venue while verification runs.</li><li>• Allow precise location access when prompted.</li><li>• Keep your face visible in a well-lit area.</li></ul><button className="button-primary mt-6" type="button" onClick={captureLocation}>Begin verification</button></div>}
          {step === 'location' && <div className="mt-6" role="status"><h3 className="font-semibold text-slate-950">{error ? 'Location check unsuccessful' : 'Checking your location…'}</h3><p className="mt-2 text-sm text-slate-600">{error ? 'Review your browser permission and try the location check again.' : 'Your browser may ask for permission. This can take a few seconds.'}</p>{error && <div className="mt-5 flex flex-wrap gap-3"><button className="button-secondary" type="button" onClick={captureLocation}>Try location again</button>{isMockMode && <button className="button-primary" type="button" onClick={useDemoLocation}>Use demo location</button>}</div>}{error && isMockMode && <p className="mt-3 text-xs text-slate-500">Demo location uses the NTU test coordinates and is available only while mock mode is active.</p>}</div>}
          {step === 'camera' && <div className="mt-6"><h3 className="font-semibold text-slate-950">Camera verification</h3><p className="mt-2 text-sm text-slate-600">Centre your face and look directly at the camera. In mock mode, confirming the preview completes the liveness step.</p><div className="mt-5 overflow-hidden rounded-2xl bg-slate-950"><video ref={videoRef} className="aspect-video w-full object-cover" autoPlay muted playsInline /></div><div className="mt-5 flex flex-wrap gap-3"><button className="button-secondary" type="button" onClick={() => void startVerification()}>Start camera</button><button className="button-primary" type="button" disabled={!cameraActive} onClick={completeVerification}>Confirm verification</button></div></div>}
          {(step === 'ready' || step === 'submitting') && <div className="mt-6"><h3 className="font-semibold text-slate-950">Ready to submit</h3><dl className="mt-4 grid gap-4 rounded-xl bg-slate-50 p-4 text-sm sm:grid-cols-2"><div><dt className="text-slate-500">Location accuracy</dt><dd className="mt-1 font-semibold text-slate-900">{position ? `${Math.round(position.accuracy)} m` : 'Unavailable'}</dd></div><div><dt className="text-slate-500">Camera verification</dt><dd className="mt-1 font-semibold text-emerald-700">Completed</dd></div></dl><p className="mt-4 text-sm leading-6 text-slate-600">By submitting, you confirm that you are physically present at this session.</p><button className="button-primary mt-6" type="button" disabled={step === 'submitting'} onClick={() => void submit()}>{step === 'submitting' ? 'Submitting…' : 'Submit check-in'}</button></div>}
          {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</div>}
        </section>
      )}
    </div></AppShell></ProtectedRoute>
  )
}

export default function CheckInPage() {
  return (
    <Suspense fallback={<AppShell><div className="card mx-auto max-w-3xl text-sm text-slate-500">Loading check-in…</div></AppShell>}>
      <CheckInFlow />
    </Suspense>
  )
}
