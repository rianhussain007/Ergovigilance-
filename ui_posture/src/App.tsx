import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import Layout from './components/Layout';
import { SearchModal } from './components/common/SearchModal';
import { RouteErrorBoundary } from './components/RouteErrorBoundary';
import { useAuth } from './auth/AuthContext';

// ── Route code-splitting ──────────────────────────────────────────────────
// Each page is loaded on demand via React.lazy, so the initial bundle stays
// small and factory PCs (slow disks, shared machines) paint fast. A shared
// Suspense fallback keeps the shell responsive while a route's chunk loads.
// Public/auth pages are tiny and always needed near startup, so they stay
// eager; every authed page below is lazy.
const LandingPage = lazy(() => import('./pages/LandingPage'));
const RequestPilot = lazy(() => import('./pages/RequestPilot'));
const ValidationPage = lazy(() => import('./pages/ValidationPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const ForgotPassword = lazy(() => import('./pages/ForgotPassword'));
const SignupPage = lazy(() => import('./pages/SignupPage'));
const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const LiveMonitoring = lazy(() => import('./pages/LiveMonitoring'));
const VideoReviewPage = lazy(() => import('./pages/VideoReviewPage'));
const ReplayPage = lazy(() => import('./pages/ReplayPage'));
const AnalyticsPage = lazy(() => import('./pages/AnalyticsPage'));
const SessionHistory = lazy(() => import('./pages/SessionHistory'));
const ReportsPage = lazy(() => import('./pages/ReportsPage'));
const SettingsPage = lazy(() => import('./pages/SettingsPage'));
const ManagerDashboard = lazy(() => import('./pages/ManagerDashboard'));
const DeploymentCenter = lazy(() => import('./pages/DeploymentCenter'));
const MultiCameraView = lazy(() => import('./pages/MultiCameraView'));
const AuditTrail = lazy(() => import('./pages/AuditTrail'));
const WorkersPage = lazy(() => import('./pages/WorkersPage'));
const WorkerSelfView = lazy(() => import('./pages/WorkerSelfView'));
const UsersPage = lazy(() => import('./pages/UsersPage'));
const PilotRequestsPage = lazy(() => import('./pages/PilotRequestsPage'));
const SetupWizardPage = lazy(() => import('./pages/SetupWizardPage'));
const ApiDocsPage = lazy(() => import('./pages/ApiDocsPage'));
const CloudCamerasPage = lazy(() => import('./pages/CloudCamerasPage'));
const CloudSettingsPage = lazy(() => import('./pages/CloudSettingsPage'));
const PricingPage = lazy(() => import('./pages/PricingPage'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const ModelDashboardPage = lazy(() => import('./pages/ModelDashboardPage'));
const YoloDemoPage = lazy(() => import('./pages/YoloDemoPage'));
const ROIAnalyticsPage = lazy(() => import('./pages/ROIAnalyticsPage'));
const SystemHealthPage = lazy(() => import('./pages/SystemHealthPage'));
const OnboardingChecklistPage = lazy(() => import('./pages/OnboardingChecklistPage'));
const CloudOnboardingPage = lazy(() => import('./pages/CloudOnboardingPage'));
const StatusPage = lazy(() => import('./pages/StatusPage'));
const ArchitecturePage = lazy(() => import('./pages/ArchitecturePage'));
const WebCamDemo = lazy(() => import('./pages/WebCamDemo'));
const ModelCardPage = lazy(() => import('./pages/ModelCardPage'));
const ConsentPage = lazy(() => import('./pages/ConsentPage'));
const PilotChecklistPage = lazy(() => import('./pages/PilotChecklistPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

function HomeRoute() {
  const { user } = useAuth();
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  return <LandingPage />;
}

function AppSuspense({ children }: { children: React.ReactNode }) {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-[#0b0f14]">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <RouteErrorBoundary>
        <AppSuspense>
          <Routes>
            <Route path="/" element={<HomeRoute />} />
            <Route path="/request-pilot" element={<RequestPilot />} />
            <Route path="/validation" element={<ValidationPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route element={<Layout />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/monitoring" element={<LiveMonitoring />} />
              <Route path="/video-review" element={<VideoReviewPage />} />
              <Route path="/replay/:sessionId" element={<ReplayPage />} />
              <Route path="/analytics" element={<AnalyticsPage />} />
              <Route path="/sessions" element={<SessionHistory />} />
              <Route path="/trends" element={<Navigate to="/reports?view=risk-trend" replace />} />
              <Route path="/reports" element={<ReportsPage />} />
              <Route path="/settings" element={<SettingsPage />} />
              <Route path="/manager" element={<ManagerDashboard />} />
              <Route path="/deployment" element={<DeploymentCenter />} />
              <Route path="/cameras" element={<MultiCameraView />} />
              <Route path="/audit" element={<AuditTrail />} />
              <Route path="/workers" element={<WorkersPage />} />
              <Route path="/my-posture" element={<WorkerSelfView />} />
              <Route path="/users" element={<UsersPage />} />
              <Route path="/pilot-requests" element={<PilotRequestsPage />} />
              <Route path="/setup" element={<SetupWizardPage />} />
              <Route path="/api-docs" element={<ApiDocsPage />} />
              <Route path="/cloud-cameras" element={<CloudCamerasPage />} />
              <Route path="/cloud-settings" element={<CloudSettingsPage />} />
              <Route path="/cloud-onboarding" element={<CloudOnboardingPage />} />
              <Route path="/model-dashboard" element={<ModelDashboardPage />} />
              <Route path="/yolo-demo" element={<YoloDemoPage />} />
              <Route path="/roi-analytics" element={<ROIAnalyticsPage />} />
              <Route path="/system-health" element={<SystemHealthPage />} />
              <Route path="/architecture" element={<ArchitecturePage />} />
              <Route path="/webcam-demo" element={<WebCamDemo />} />
              <Route path="/model-card" element={<ModelCardPage />} />
              <Route path="/pilot-checklist" element={<PilotChecklistPage />} />
              <Route path="/onboarding" element={<OnboardingChecklistPage />} />
              <Route path="/consent" element={<ConsentPage />} />
              {/* Catch-all: unknown URLs get an in-shell 404 instead of a
                  blank screen. Explicit routes above always win the match. */}
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route path="/pricing" element={<PricingPage />} />
            <Route path="/legal" element={<LegalPage />} />
            <Route path="/status" element={<StatusPage />} />
          </Routes>
        </AppSuspense>
      </RouteErrorBoundary>
      <SearchModal />
    </BrowserRouter>
  );
}
