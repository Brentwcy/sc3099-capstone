const steps = ['Account', 'Consent', 'Face enrollment']

export function OnboardingProgress({ currentStep, completedSteps = currentStep - 1 }: { currentStep: 1 | 2 | 3; completedSteps?: number }) {
  return (
    <ol className="grid gap-2 sm:grid-cols-3" aria-label="Account setup progress">
      {steps.map((step, index) => {
        const number = index + 1
        const current = number === currentStep
        const complete = number <= completedSteps && !current
        return (
          <li key={step} className={`rounded-xl border px-4 py-3 text-sm font-semibold ${current ? 'border-blue-300 bg-blue-50 text-blue-900' : complete ? 'border-emerald-200 bg-emerald-50 text-emerald-800' : 'border-slate-200 bg-white text-slate-500'}`} aria-current={current ? 'step' : undefined}>
            {complete ? '✓' : number}. {step}
          </li>
        )
      })}
    </ol>
  )
}
