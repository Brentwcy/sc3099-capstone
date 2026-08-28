import { MIN_PASSWORD_LENGTH } from '@/lib/auth/validation'

export function PasswordRequirements({ password }: { password: string }) {
  const longEnough = password.length >= MIN_PASSWORD_LENGTH

  return (
    <div className="mt-2 text-xs" aria-live="polite">
      <p className="font-medium text-slate-600">Password requirement</p>
      <p className={`mt-1 ${longEnough ? 'text-emerald-700' : 'text-slate-500'}`}>
        <span aria-hidden="true">{longEnough ? '✓' : '○'}</span>{' '}
        At least {MIN_PASSWORD_LENGTH} characters
      </p>
    </div>
  )
}
