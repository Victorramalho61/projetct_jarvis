import { lazy } from "react";
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
const FreshserviceProjectsPage = lazy(() => import("./pages/FreshserviceProjectsPage"));
const FreshserviceProjectDetailPage = lazy(() => import("./pages/FreshserviceProjectDetailPage"));
const MoneypennyPage = lazy(() => import("./pages/MoneypennyPage"));
const PerformancePage = lazy(() => import("./pages/PerformancePage"));
const FiscalPage = lazy(() => import("./pages/admin/FiscalPage"));
const BennerIntegracaoPage = lazy(() => import("./pages/admin/BennerIntegracaoPage"));
const BennerEvolucaoPage = lazy(() => import("./pages/admin/BennerEvolucaoPage"));
const HermesPage = lazy(() => import("./pages/admin/HermesPage"));
const PublicEvaluationPage = lazy(() => import("./pages/PublicEvaluationPage"));
const PublicCienciaPage = lazy(() => import("./pages/PublicCienciaPage"));
const PublicCienciaPresencialPage = lazy(() => import("./pages/PublicCienciaPresencialPage"));
const PublicSelfEvaluationPage = lazy(() => import("./pages/PublicSelfEvaluationPage"));
const PublicAutoAvaliacaoPresencialPage = lazy(() => import("./pages/PublicAutoAvaliacaoPresencialPage"));
const CartaoPage = lazy(() => import("./pages/CartaoPage"));
const FinanceiroPage = lazy(() => import("./pages/FinanceiroPage"));
const ExperienciaPage = lazy(() => import("./pages/ExperienciaPage"));
const PublicExperienciaPage = lazy(() => import("./pages/PublicExperienciaPage"));

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
          {/* Rotas públicas de avaliação — com e sem prefixo /desempenho/ */}
          <Route path="/avaliar/:token" element={<PublicEvaluationPage />} />
          <Route path="/desempenho/avaliar/:token" element={<PublicEvaluationPage />} />
          <Route path="/ciencia/:token" element={<PublicCienciaPage />} />
          <Route path="/desempenho/ciencia/:token" element={<PublicCienciaPage />} />
          <Route path="/ciencia-presencial" element={<PublicCienciaPresencialPage />} />
          <Route path="/desempenho/ciencia-presencial" element={<PublicCienciaPresencialPage />} />
          <Route path="/auto-avaliar/:token" element={<PublicSelfEvaluationPage />} />
          <Route path="/desempenho/auto-avaliar/:token" element={<PublicSelfEvaluationPage />} />
          <Route path="/auto-avaliacao-presencial" element={<PublicAutoAvaliacaoPresencialPage />} />
          <Route path="/desempenho/auto-avaliacao-presencial" element={<PublicAutoAvaliacaoPresencialPage />} />
          <Route path="/experiencia/avaliar/:token" element={<PublicExperienciaPage />} />

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
            <Route path="/freshservice/projetos" element={<FreshserviceProjectsPage />} />
            <Route path="/freshservice/projetos/:id" element={<FreshserviceProjectDetailPage />} />
            {/* Módulo de Agentes consolidado — abas via ?tab= */}
            <Route path="/admin/agentes" element={<AgentsDashboard />} />
            <Route path="/admin/gastos" element={<ExpensesPage />} />
            <Route path="/admin/fiscal" element={<FiscalPage />} />
            <Route path="/admin/benner" element={<BennerIntegracaoPage />} />
            <Route path="/admin/benner-evolucao" element={<BennerEvolucaoPage />} />
            <Route path="/admin/governanca" element={<GovernancePage />} />
            <Route path="/admin/payfly" element={<PayFlyPage />} />
            <Route path="/admin/proposals" element={<ProposalsPage />} />
            <Route path="/admin/cto-inbox" element={<CTOInboxPage />} />
            <Route path="/admin/orquestrador" element={<OrchestratorPage />} />
            <Route path="/admin/hermes" element={<HermesPage />} />
            <Route path="/desempenho" element={<PerformancePage />} />
            <Route path="/cartoes" element={<CartaoPage />} />
            <Route path="/financeiro" element={<FinanceiroPage />} />
            <Route path="/experiencia" element={<ExperienciaPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
    </ThemeProvider>
  );
}
