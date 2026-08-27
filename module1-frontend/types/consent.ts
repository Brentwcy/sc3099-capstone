export type PermissionState =
  | 'not-requested'
  | 'prompt'
  | 'granted'
  | 'denied'
  | 'unavailable'
  | 'insecure-context'
  | 'checking'
  | 'error'

export interface UpdateConsentRequest {
  camera_consent?: boolean
  geolocation_consent?: boolean
}

export type DiagnosticError =
  | 'permission-denied'
  | 'device-not-found'
  | 'device-in-use'
  | 'timeout'
  | 'unsupported'
  | 'insecure-context'
  | 'unknown'

export interface DeviceDiagnosticResult {
  state: PermissionState
  message: string
  checkedAt?: string
  accuracyMeters?: number
  error?: DiagnosticError
}

export interface StoredDeviceDiagnostics {
  camera?: DeviceDiagnosticResult
  location?: DeviceDiagnosticResult
}
