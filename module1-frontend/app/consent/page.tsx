import { AppShell } from '@/components/app-shell'
import { FeaturePlaceholder } from '@/components/feature-placeholder'
import { ProtectedRoute } from '@/components/protected-route'

export default function ConsentPage() {
  return <ProtectedRoute><AppShell><FeaturePlaceholder title="Privacy and consent" description="Camera and geolocation explanations, preferences, and permission handling will be implemented in Week 4." /></AppShell></ProtectedRoute>
}
