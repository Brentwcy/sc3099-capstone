'use client'

import { useState } from 'react'
import { useAuth } from '@/contexts/auth-context'
import { getApiErrorMessage } from '@/lib/api/client'

export function ConsentControls() {
  const { user, updateConsent } = useAuth()
  const [isSaving, setIsSaving] = useState(false)
  const [saveMessage, setSaveMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null)

  const saveConsent = async (field: 'camera_consent' | 'geolocation_consent', value: boolean) => {
    setSaveMessage(null)
    setIsSaving(true)
    try {
      await updateConsent({ [field]: value })
      setSaveMessage({ text: 'Consent preference saved.', type: 'success' })
    } catch (error) {
      setSaveMessage({ text: getApiErrorMessage(error), type: 'error' })
    } finally {
      setIsSaving(false)
    }
  }

  const controls = [
    {
      field: 'camera_consent' as const,
      title: 'Camera and face-processing consent',
      description: 'Allow SAIV to capture and process a face image for liveness and identity verification.',
      consequence: 'Turning this off prevents face enrollment and attendance check-in.',
      checked: Boolean(user?.camera_consent),
    },
    {
      field: 'geolocation_consent' as const,
      title: 'Location-processing consent',
      description: 'Allow SAIV to capture your current location when you start an attendance check-in.',
      consequence: 'Turning this off prevents attendance check-in.',
      checked: Boolean(user?.geolocation_consent),
    },
  ]

  return (
    <div>
      <div className="grid gap-4 md:grid-cols-2">
        {controls.map((item) => (
          <label key={item.field} className="card flex cursor-pointer items-start justify-between gap-5">
            <span>
              <span className="block font-semibold text-slate-950">{item.title}</span>
              <span className="mt-2 block text-sm leading-6 text-slate-600">{item.description}</span>
              <span className="mt-2 block text-xs font-medium text-amber-800">{item.consequence}</span>
            </span>
            <input
              className="mt-1 h-5 w-5 shrink-0 accent-blue-700"
              type="checkbox"
              role="switch"
              checked={item.checked}
              disabled={isSaving}
              onChange={(event) => void saveConsent(item.field, event.target.checked)}
            />
          </label>
        ))}
      </div>
      <p className="mt-3 min-h-6 text-sm" aria-live="polite">
        {isSaving
          ? <span className="text-blue-700">Saving consent…</span>
          : saveMessage
            ? <span className={saveMessage.type === 'success' ? 'text-emerald-700' : 'text-red-700'}>{saveMessage.text}</span>
            : null}
      </p>
    </div>
  )
}
