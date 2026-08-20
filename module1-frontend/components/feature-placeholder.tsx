import Link from 'next/link'

export function FeaturePlaceholder({ title, description }: { title: string; description: string }) {
  return (
    <section className="card mx-auto max-w-2xl text-center">
      <p className="eyebrow">Foundation ready</p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight text-slate-950">{title}</h1>
      <p className="mx-auto mt-4 max-w-xl text-slate-600">{description}</p>
      <Link href="/dashboard" className="button-secondary mt-8 inline-flex">
        Back to dashboard
      </Link>
    </section>
  )
}
