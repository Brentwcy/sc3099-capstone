'use client'

import Link from 'next/link'
import { AppShell } from '@/components/app-shell'
import { useAuth } from '@/contexts/auth-context'

export default function Home() {
  const { user, isLoading } = useAuth()

  return (
    <AppShell>
      <section className="grid items-center gap-12 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:py-20">
        <div>
          <p className="eyebrow">Secure attendance made simple</p>
          <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight text-slate-950 sm:text-6xl">
            Check in with confidence, from your phone or laptop.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
            SAIV combines consent-first camera access, location verification, and secure face
            verification in one student-friendly workflow.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {isLoading ? (
              <div className="flex gap-3" role="status" aria-label="Loading account actions">
                <span className="h-11 w-24 animate-pulse rounded-lg bg-slate-200" />
                <span className="h-11 w-36 animate-pulse rounded-lg bg-slate-200" />
              </div>
            ) : (
              <>
                <Link href={user ? '/sessions' : '/login'} className="button-primary">Check in</Link>
                {!user && <Link href="/register" className="button-secondary">Create account</Link>}
              </>
            )}
          </div>
        </div>

        <div id="check-in-process" className="card scroll-mt-6 bg-slate-950 text-white shadow-xl shadow-slate-300/60">
          <p className="text-sm font-semibold text-blue-300">How check-in works</p>
          <h2 className="mt-3 text-2xl font-semibold">A clear, guided process</h2>
          <ol className="mt-8 space-y-5">
            {['Choose an active class session', 'Start camera and location verification', 'Complete face verification and submit'].map((step, index) => (
              <li key={step} className="flex items-start gap-4">
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-blue-600 text-sm font-bold">{index + 1}</span>
                <span className="pt-1 text-slate-200">{step}</span>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section id="how-it-works" className="grid gap-4 pb-12 sm:grid-cols-3">
        {[
          ['Private by design', 'Your consent is requested before camera or location access.'],
          ['Works on your device', 'The responsive workflow is designed for phones and laptops used during class.'],
          ['Clear outcomes', 'See whether a check-in is approved, pending, flagged, or rejected.'],
        ].map(([title, description]) => (
          <article key={title} className="card">
            <h2 className="font-semibold text-slate-950">{title}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">{description}</p>
          </article>
        ))}
      </section>
    </AppShell>
  );
}
