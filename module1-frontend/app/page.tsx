import Link from 'next/link'
import { AppShell } from '@/components/app-shell'

export default function Home() {
  return (
    <AppShell>
      <section className="grid items-center gap-12 py-10 lg:grid-cols-[1.15fr_0.85fr] lg:py-20">
        <div>
          <p className="eyebrow">Secure attendance made simple</p>
          <h1 className="mt-4 max-w-3xl text-4xl font-bold tracking-tight text-slate-950 sm:text-6xl">
            Check in with confidence, right from your phone.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-600">
            SAIV combines consent-first camera access, location verification, and secure identity
            checks in one student-friendly workflow.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Link href="/login" className="button-primary">Continue to login</Link>
            <a href="#how-it-works" className="button-secondary">How it works</a>
          </div>
        </div>

        <div className="card bg-slate-950 text-white shadow-xl shadow-slate-300/60">
          <p className="text-sm font-semibold text-blue-300">Your next check-in</p>
          <h2 className="mt-3 text-2xl font-semibold">A clear, guided process</h2>
          <ol className="mt-8 space-y-5">
            {['Choose an active class session', 'Grant camera and location consent', 'Complete verification and submit'].map((step, index) => (
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
          ['Mobile friendly', 'The responsive workflow is designed for use during class.'],
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
