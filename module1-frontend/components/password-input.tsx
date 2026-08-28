'use client'

import { InputHTMLAttributes, useState } from 'react'

type PasswordInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'type'>

export function PasswordInput({ className = '', ...props }: PasswordInputProps) {
  const [isVisible, setIsVisible] = useState(false)
  const action = isVisible ? 'Hide password' : 'Show password'

  return (
    <div className="relative">
      <input {...props} type={isVisible ? 'text' : 'password'} className={`${className} pr-12`} />
      <button
        className="absolute inset-y-0 right-0 grid w-12 place-items-center rounded-r-lg text-slate-500 transition hover:text-slate-900"
        type="button"
        aria-label={action}
        aria-pressed={isVisible}
        onClick={() => setIsVisible((visible) => !visible)}
      >
        {isVisible ? (
          <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="m3 3 18 18" />
            <path d="M10.6 10.7a2 2 0 0 0 2.7 2.7" />
            <path d="M9.9 4.2A10.8 10.8 0 0 1 12 4c5.5 0 9 6 9 6a17.7 17.7 0 0 1-2.1 2.8M6.6 6.6C4.4 8.1 3 10 3 10s3.5 6 9 6a9.7 9.7 0 0 0 3.4-.6" />
          </svg>
        ) : (
          <svg aria-hidden="true" className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        )}
      </button>
    </div>
  )
}
