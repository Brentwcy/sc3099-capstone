import type { DeviceDiagnosticResult, PermissionState, StoredDeviceDiagnostics } from '@/types/consent'

const DIAGNOSTICS_KEY = 'saiv.device.diagnostics'
export const DIAGNOSTICS_CHANGE_EVENT = 'saiv:device-diagnostics-change'

const result = (
  state: PermissionState,
  message: string,
  details: Partial<DeviceDiagnosticResult> = {},
): DeviceDiagnosticResult => ({ state, message, ...details })

export function isSecureBrowserContext() {
  return typeof window !== 'undefined' && window.isSecureContext
}

export function getStoredDiagnostics(): StoredDeviceDiagnostics {
  if (typeof window === 'undefined') return {}
  try {
    const stored = window.sessionStorage.getItem(DIAGNOSTICS_KEY)
    return stored ? (JSON.parse(stored) as StoredDeviceDiagnostics) : {}
  } catch {
    window.sessionStorage.removeItem(DIAGNOSTICS_KEY)
    return {}
  }
}

export function storeDiagnostic(kind: keyof StoredDeviceDiagnostics, diagnostic: DeviceDiagnosticResult) {
  const diagnostics = { ...getStoredDiagnostics(), [kind]: diagnostic }
  window.sessionStorage.setItem(DIAGNOSTICS_KEY, JSON.stringify(diagnostics))
  window.dispatchEvent(new Event(DIAGNOSTICS_CHANGE_EVENT))
}

export async function queryInitialPermission(name: 'camera' | 'geolocation'): Promise<DeviceDiagnosticResult> {
  if (!isSecureBrowserContext()) {
    return result('insecure-context', 'Secure HTTPS access is required for this browser feature.', { error: 'insecure-context' })
  }
  if (!navigator.permissions?.query) return result('not-requested', 'Permission has not been tested in this tab.')

  try {
    const status = await navigator.permissions.query({ name: name as PermissionName })
    const state = status.state as 'granted' | 'denied' | 'prompt'
    return result(state, state === 'granted'
      ? 'Browser permission is granted. Test access to confirm the device is available.'
      : state === 'denied'
        ? 'Permission is blocked in browser settings.'
        : 'The browser will ask when you test access.')
  } catch {
    return result('not-requested', 'Permission status is unavailable until access is tested.')
  }
}

export async function testCameraAccess(): Promise<DeviceDiagnosticResult> {
  if (!isSecureBrowserContext()) {
    return result('insecure-context', 'Open SAIV over HTTPS or localhost to use the camera.', { error: 'insecure-context' })
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    return result('unavailable', 'Camera access is not supported by this browser or device.', { error: 'unsupported' })
  }

  let stream: MediaStream | undefined
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true })
    return result('granted', 'Camera access works. The test stream has been closed.', { checkedAt: new Date().toISOString() })
  } catch (error) {
    const name = error instanceof DOMException ? error.name : ''
    if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
      return result('denied', 'Camera access is blocked. Enable it in your browser site settings.', { error: 'permission-denied', checkedAt: new Date().toISOString() })
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      return result('unavailable', 'No camera was found on this device.', { error: 'device-not-found', checkedAt: new Date().toISOString() })
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      return result('error', 'The camera may be in use by another application.', { error: 'device-in-use', checkedAt: new Date().toISOString() })
    }
    return result('error', 'Camera access could not be tested.', { error: 'unknown', checkedAt: new Date().toISOString() })
  } finally {
    stream?.getTracks().forEach((track) => track.stop())
  }
}

export async function testLocationAccess(): Promise<DeviceDiagnosticResult> {
  if (!isSecureBrowserContext()) {
    return result('insecure-context', 'Open SAIV over HTTPS or localhost to use location.', { error: 'insecure-context' })
  }
  if (!navigator.geolocation) {
    return result('unavailable', 'Geolocation is not supported by this browser or device.', { error: 'unsupported' })
  }

  return new Promise((resolve) => {
    navigator.geolocation.getCurrentPosition(
      (position) => resolve(result('granted', `Location access works (accuracy: ${Math.round(position.coords.accuracy)} m).`, {
        accuracyMeters: position.coords.accuracy,
        checkedAt: new Date().toISOString(),
      })),
      (error) => {
        const checkedAt = new Date().toISOString()
        if (error.code === error.PERMISSION_DENIED) {
          resolve(result('denied', 'Location access is blocked. Enable it in your browser site settings.', { error: 'permission-denied', checkedAt }))
        } else if (error.code === error.POSITION_UNAVAILABLE) {
          resolve(result('unavailable', 'Your device could not determine its location.', { error: 'device-not-found', checkedAt }))
        } else {
          resolve(result('error', 'The location request timed out. Move to an open area and try again.', { error: 'timeout', checkedAt }))
        }
      },
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 0 },
    )
  })
}
