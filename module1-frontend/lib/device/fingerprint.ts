const FINGERPRINT_KEY = 'saiv.device.fingerprint'

export function getDeviceFingerprint() {
  const existing = window.localStorage.getItem(FINGERPRINT_KEY)
  if (existing) return existing

  const value = `web_${crypto.randomUUID().replaceAll('-', '')}`
  window.localStorage.setItem(FINGERPRINT_KEY, value)
  return value
}
