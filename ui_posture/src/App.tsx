import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import LiveMonitoring from './pages/LiveMonitoring';
import AnalyticsPage from './pages/AnalyticsPage';
import SessionHistory from './pages/SessionHistory';
import ReportsPage from './pages/ReportsPage';
import SettingsPage from './pages/SettingsPage';
import ManagerDashboard from './pages/ManagerDashboard';
import DeploymentCenter from './pages/DeploymentCenter';
import MultiCameraView from './pages/MultiCameraView';
import AuditTrail from './pages/AuditTrail';
import WorkersPage from './pages/WorkersPage';
import UsersPage from './pages/UsersPage';
import PilotRequestsPage from './pages/PilotRequestsPage';
import { SearchModal } from './components/common/SearchModal';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import VideoReviewPage from './pages/VideoReviewPage';
import ReplayPage from './pages/ReplayPage';
import LandingPage from './pages/LandingPage';
import RequestPilot from './pages/RequestPilot';
import { useAuth } from './auth/AuthContext';

function HomeRoute() {
  const { user } = useAuth();
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }
  return <LandingPage />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomeRoute />} />
        <Route path="/request-pilot" element={<RequestPilot />} />
        <Route path="/login" element={<LoginPage />} />
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
          <Route path="/users" element={<UsersPage />} />
          <Route path="/pilot-requests" element={<PilotRequestsPage />} />
        </Route>
      </Routes>
      <SearchModal />
    </BrowserRouter>
  );
}
