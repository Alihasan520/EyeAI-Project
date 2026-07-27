import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "./components/layout/AppShell";
import { ProtectedRoute } from "./components/shared/ProtectedRoute";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PatientDetailPage } from "./pages/PatientDetailPage";
import { PatientsPage } from "./pages/PatientsPage";
import { AnalysisPage } from "./pages/AnalysisPage";
import { AssistantPage } from "./pages/AssistantPage";
import { AlertsPage } from "./pages/AlertsPage";
import { ReportsPage } from "./pages/ReportsPage";
import { ProfilePage } from "./pages/ProfilePage";
import { SystemPage } from "./pages/SystemPage";
import { UsersAccessPage } from "./pages/UsersAccessPage";
import { VisitsPage } from "./pages/VisitsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="patients" element={<PatientsPage />} />
        <Route path="patients/:patientRef" element={<PatientDetailPage />} />
        <Route path="visits" element={<VisitsPage />} />
        <Route path="profile" element={<ProfilePage />} />
        <Route path="system" element={<SystemPage />} />
        <Route path="system/users" element={<UsersAccessPage />} />
        <Route path="analysis" element={<AnalysisPage />} />
        <Route path="assistant" element={<AssistantPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="reports" element={<ReportsPage />} />
      </Route>
      <Route path="/home" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
