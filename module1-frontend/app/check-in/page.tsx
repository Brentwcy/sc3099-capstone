import { AppShell } from '@/components/app-shell'
import { FeaturePlaceholder } from '@/components/feature-placeholder'
import { ProtectedRoute } from '@/components/protected-route'

export default function CheckInPage() {
  return <ProtectedRoute><AppShell><FeaturePlaceholder title="Check-in workflow" description="Active sessions, liveness prompts, location capture, and submission will be built on this route during Weeks 4–5." /></AppShell></ProtectedRoute>
}
