import { AppShell } from '@/components/app-shell'
import { FeaturePlaceholder } from '@/components/feature-placeholder'
import { ProtectedRoute } from '@/components/protected-route'

export default function HistoryPage() {
  return <ProtectedRoute><AppShell><FeaturePlaceholder title="Attendance history" description="This route is reserved for the student's check-in records after the core workflow is integrated." /></AppShell></ProtectedRoute>
}
