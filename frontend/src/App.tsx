import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RequestAccessPage from "./pages/RequestAccessPage";
import HomePage from "./pages/HomePage";
import AccessManagementPage from "./pages/admin/AccessManagementPage";
import LogsPage from "./pages/admin/LogsPage";
import MonitoringPage from "./pages/admin/MonitoringPage";
import SystemDetailPage from "./pages/admin/SystemDetailPage";
import FreshservicePage from "./pages/FreshservicePage";
import AgentsDashboard from "./pages/admin/AgentsDashboard";
import MoneypennyPage from "./pages/MoneypennyPage";
import ProfilePage from "./pages/ProfilePage";
import InitializePasswordPage from "./pages/InitializePasswordPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ExpensesPage from "./pages/admin/ExpensesPage";

export default function App() {
  return (
    <ThemeProvider>
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/solicitar-acesso" element={<RequestAccessPage />} />
          <Route path="/definir-senha" element={<InitializePasswordPage />} />
          <Route path="/esqueci-senha" element={<ForgotPasswordPage />} />
          <Route path="/redefinir-senha" element={<ResetPasswordPage />} />

          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route path="/" element={<HomePage />} />
            <Route path="/moneypenny" element={<MoneypennyPage />} />
            <Route path="/perfil" element={<ProfilePage />} />
            <Route path="/admin/acesso" element={<AccessManagementPage />} />
            <Route path="/admin/logs" element={<LogsPage />} />
            <Route path="/admin/monitoramento" element={<MonitoringPage />} />
            <Route path="/admin/monitoramento/:id" element={<SystemDetailPage />} />
            <Route path="/freshservice" element={<FreshservicePage />} />
            {/* Módulo de Agentes consolidado — abas via ?tab= */}
            <Route path="/admin/agentes" element={<AgentsDashboard />} />
            <Route path="/admin/gastos" element={<ExpensesPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
    </ThemeProvider>
  );
}
