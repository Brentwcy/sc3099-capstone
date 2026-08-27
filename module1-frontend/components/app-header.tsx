'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { useAuth } from '@/contexts/auth-context'

const links = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/sessions', label: 'Sessions' },
  { href: '/history', label: 'History' },
]

export function AppHeader() {
  const pathname = usePathname()
  const router = useRouter()
  const { user, logout } = useAuth()

  const handleLogout = () => {
    logout()
    router.push('/')
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3" aria-label="SAIV home">
          <span className="grid h-10 w-10 place-items-center rounded-xl bg-blue-700 font-bold text-white">
            S
          </span>
          <span>
            <span className="block font-semibold text-slate-950">SAIV</span>
            <span className="block text-xs text-slate-500">Student attendance</span>
          </span>
        </Link>

        {user ? (
          <div className="flex flex-wrap items-center justify-end gap-2">
            <nav className="flex items-center gap-1" aria-label="Main navigation">
              {links.map((link) => (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                    pathname === link.href
                      ? 'bg-blue-50 text-blue-800'
                      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                  }`}
                >
                  {link.label}
                </Link>
              ))}
            </nav>
            <div className="flex items-center gap-2 sm:ml-2 sm:border-l sm:border-slate-200 sm:pl-4">
              <Link
                href="/settings"
                className={`rounded-lg px-3 py-2 text-sm font-medium transition ${
                  pathname === '/settings'
                    ? 'bg-blue-50 text-blue-800'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
              >
                Settings
              </Link>
              <button className="button-secondary" type="button" onClick={handleLogout}>
                Log out
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <Link className="button-secondary" href="/register">Register</Link>
            <Link className="button-primary" href="/login">Student login</Link>
          </div>
        )}
      </div>
    </header>
  )
}
