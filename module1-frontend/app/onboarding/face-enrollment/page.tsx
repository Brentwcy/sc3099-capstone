'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { AppShell } from '@/components/app-shell'
import { OnboardingProgress } from '@/components/onboarding-progress'
import { ProtectedRoute } from '@/components/protected-route'
import { useAuth } from '@/contexts/auth-context'
import { getApiErrorMessage } from '@/lib/api/client'
import { captureVideoFrame } from '@/lib/device/camera'

export default function FaceEnrollmentPage() {
  const { user, enrollFace } = useAuth()
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [cameraActive, setCameraActive] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const consentComplete = Boolean(user?.camera_consent && user.geolocation_consent)

  const stopCamera = () => {
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    setCameraActive(false)
  }

  useEffect(() => () => streamRef.current?.getTracks().forEach((track) => track.stop()), [])

  const startCamera = async () => {
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

  const submitEnrollment = async () => {
    if (!videoRef.current) return
    setError('')
    setIsSubmitting(true)
    try {
      const image = captureVideoFrame(videoRef.current)
      await enrollFace(image)
      stopCamera()
    } catch (enrollmentError) {
      setError(getApiErrorMessage(enrollmentError))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <ProtectedRoute>
      <AppShell>
        <div className="mx-auto max-w-4xl">
          <OnboardingProgress currentStep={3} completedSteps={user?.face_enrolled ? 3 : consentComplete ? 2 : 1} />
          <section className="card mt-8">
            <p className="eyebrow">Account setup</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-slate-950">Face enrollment</h1>
            <p className="mt-3 max-w-2xl leading-7 text-slate-600">Capture one clear, front-facing image. The image is processed in memory and only a privacy-preserving template hash is retained.</p>

            {!consentComplete ? (
              <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">Camera and location consent must be completed before face enrollment. <Link className="font-semibold underline" href="/onboarding/consent">Review consent</Link>.</div>
            ) : user?.face_enrolled ? (
              <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-900">
                <h2 className="font-semibold">Face enrollment complete</h2>
                <p className="mt-2 text-sm">Your account is ready for attendance verification.</p>
              </div>
            ) : (
              <>
                <div className="mt-6 overflow-hidden rounded-2xl bg-slate-950">
                  <video ref={videoRef} className="aspect-video w-full object-cover" autoPlay muted playsInline />
                </div>
                <div className="mt-5 flex flex-wrap gap-3">
                  {!cameraActive ? (
                    <button className="button-secondary" type="button" onClick={() => void startCamera()}>Start camera</button>
                  ) : (
                    <button className="button-primary" type="button" disabled={isSubmitting} onClick={() => void submitEnrollment()}>{isSubmitting ? 'Enrolling…' : 'Capture and enroll'}</button>
                  )}
                  {cameraActive && <button className="button-secondary" type="button" disabled={isSubmitting} onClick={stopCamera}>Cancel camera</button>}
                </div>
              </>
            )}

            {error && <div className="mt-5 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800" role="alert">{error}</div>}
            <div className="mt-6 flex flex-wrap gap-3">
              {user?.face_enrolled && <Link className="button-primary" href="/sessions">View sessions</Link>}
              <Link className="button-secondary" href="/dashboard">Return to dashboard</Link>
            </div>
          </section>
        </div>
      </AppShell>
    </ProtectedRoute>
  )
}
