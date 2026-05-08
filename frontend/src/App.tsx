import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import LoginPage from "./pages/LoginPage";
import RequestAccessPage from "./pages/RequestAccessPage";
import HomePage from "./pages/HomePage";
import InitializePasswordPage from "./pages/InitializePasswordPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";
import ProfilePage from "./pages/ProfilePage";

// Lazy-loaded pages: carregadas apenas quando o usuário navega até elas
const AccessManagementPage = lazy(() => import("./pages/admin/AccessManagementPage"));
const LogsPage = lazy(() => import("./pages/admin/LogsPage"));
const MonitoringPage = lazy(() => import("./pages/admin/MonitoringPage"));
const SystemDetailPage = lazy(() => import("./pages/admin/SystemDetailPage"));
const AgentsDashboard = lazy(() => import("./pages/admin/AgentsDashboard"));
const ExpensesPage = lazy(() => import("./pages/admin/ExpensesPage"));
const GovernancePage = lazy(() => import("./pages/admin/GovernancePage"));
const PayFlyPage = lazy(() => import("./pages/admin/PayFlyPage"));
const ProposalsPage = lazy(() => import("./pages/admin/ProposalsPage"));
const CTOInboxPage = lazy(() => import("./pages/admin/CTOInboxPage"));
const OrchestratorPage = lazy(() => import("./pages/admin/OrchestratorPage"));
const FreshservicePage = lazy(() => import("./pages/FreshservicePage"));
const MoneypennyPage = lazy(() => import("./pages/MoneypennyPage"));

function PageLoader() {
  return (
    <div className="flex items-center justify-center h-64">
      <div className="w-8 h-8 border-4 border-voetur-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<PageLoader />}>
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
            <Route path="/admin/governanca" element={<GovernancePage />} />
            <Route path="/admin/payfly" element={<PayFlyPage />} />
            <Route path="/admin/proposals" element={<ProposalsPage />} />
            <Route path="/admin/cto-inbox" element={<CTOInboxPage />} />
            <Route path="/admin/orquestrador" element={<OrchestratorPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
    </ThemeProvider>
  );
}
