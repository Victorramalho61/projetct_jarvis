import { Suspense } from "react";
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
import { lazyWithReload } from "./lib/lazyWithReload";

// Lazy-loaded pages: carregadas apenas quando o usuário navega até elas.
// lazyWithReload recarrega a página uma vez se o chunk não existir mais
// (hash antigo em cache após um deploy do frontend).
const AccessManagementPage = lazyWithReload(() => import("./pages/admin/AccessManagementPage"));
const LogsPage = lazyWithReload(() => import("./pages/admin/LogsPage"));
const MonitoringPage = lazyWithReload(() => import("./pages/admin/MonitoringPage"));
const SystemDetailPage = lazyWithReload(() => import("./pages/admin/SystemDetailPage"));
const ExpensesPage = lazyWithReload(() => import("./pages/admin/ExpensesPage"));
const GovernancePage = lazyWithReload(() => import("./pages/admin/GovernancePage"));
const PayFlyPage = lazyWithReload(() => import("./pages/admin/PayFlyPage"));
const FreshservicePage = lazyWithReload(() => import("./pages/FreshservicePage"));
const FreshserviceProjectsPage = lazyWithReload(() => import("./pages/FreshserviceProjectsPage"));
const FreshserviceProjectDetailPage = lazyWithReload(() => import("./pages/FreshserviceProjectDetailPage"));
const FreshserviceOverdueTasksPage = lazyWithReload(() => import("./pages/FreshserviceOverdueTasksPage"));
const MoneypennyPage = lazyWithReload(() => import("./pages/MoneypennyPage"));
const PerformancePage = lazyWithReload(() => import("./pages/PerformancePage"));
const FiscalPage = lazyWithReload(() => import("./pages/admin/FiscalPage"));
const BennerIntegracaoPage = lazyWithReload(() => import("./pages/admin/BennerIntegracaoPage"));
const BennerEvolucaoPage = lazyWithReload(() => import("./pages/admin/BennerEvolucaoPage"));
const HermesPage = lazyWithReload(() => import("./pages/admin/HermesPage"));
const PublicEvaluationPage = lazyWithReload(() => import("./pages/PublicEvaluationPage"));
const PublicCienciaPage = lazyWithReload(() => import("./pages/PublicCienciaPage"));
const PublicCienciaPresencialPage = lazyWithReload(() => import("./pages/PublicCienciaPresencialPage"));
const PublicSelfEvaluationPage = lazyWithReload(() => import("./pages/PublicSelfEvaluationPage"));
const PublicActionPlanPage = lazyWithReload(() => import("./pages/PublicActionPlanPage"));
const PublicActionPlanCheckinPage = lazyWithReload(() => import("./pages/PublicActionPlanCheckinPage"));
const PublicAutoAvaliacaoPresencialPage = lazyWithReload(() => import("./pages/PublicAutoAvaliacaoPresencialPage"));
const CartaoPage = lazyWithReload(() => import("./pages/CartaoPage"));
const FinanceiroPage = lazyWithReload(() => import("./pages/FinanceiroPage"));
const ExperienciaPage = lazyWithReload(() => import("./pages/ExperienciaPage"));
const PublicExperienciaPage = lazyWithReload(() => import("./pages/PublicExperienciaPage"));
const RhPage = lazyWithReload(() => import("./pages/RhPage"));
const RhVagasPage = lazyWithReload(() => import("./pages/RhVagasPage"));
const RhAssinaturaPage = lazyWithReload(() => import("./pages/RhAssinaturaPage"));
const RhFormularioPrintPage = lazyWithReload(() => import("./pages/RhFormularioPrintPage"));
const RhRelatorioPrintPage = lazyWithReload(() => import("./pages/RhRelatorioPrintPage"));
const SatisfacaoDashboardPage = lazyWithReload(() => import("./pages/SatisfacaoDashboardPage"));
const SatisfacaoEnvioPage = lazyWithReload(() => import("./pages/SatisfacaoEnvioPage"));
const SatisfacaoCadastroPage = lazyWithReload(() => import("./pages/SatisfacaoCadastroPage"));
const PublicSatisfacaoPage = lazyWithReload(() => import("./pages/PublicSatisfacaoPage"));

// agents-service foi removido do stack — placeholder evita que as páginas do módulo
// (que fariam polling contra o serviço inexistente) sejam montadas.
function ModuloAgentesDesativado() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center text-center px-4">
      <div>
        <p className="text-lg font-medium text-gray-600">Módulo de Agentes desativado</p>
        <p className="mt-1 text-sm text-gray-400">agents-service não está em execução.</p>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <ThemeProvider>
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={
          <div className="flex min-h-screen items-center justify-center text-sm text-gray-400">Carregando...</div>
        }>
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
          <Route path="/satisfacao/responder/:token" element={<PublicSatisfacaoPage />} />
          <Route
            path="/rh/vagas/:id/imprimir"
            element={
              <ProtectedRoute>
                <RhFormularioPrintPage />
              </ProtectedRoute>
            }
          />
          <Route
            path="/rh/relatorio"
            element={
              <ProtectedRoute>
                <RhRelatorioPrintPage />
              </ProtectedRoute>
            }
          />
          <Route path="/plano-acao/:token" element={<PublicActionPlanPage />} />
          <Route path="/desempenho/plano-acao/:token" element={<PublicActionPlanPage />} />
          <Route path="/plano-acao/checkin/:token" element={<PublicActionPlanCheckinPage />} />
          <Route path="/desempenho/plano-acao/checkin/:token" element={<PublicActionPlanCheckinPage />} />

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
            <Route path="/freshservice/projetos/estouradas" element={<FreshserviceOverdueTasksPage />} />
            <Route path="/freshservice/projetos/:id" element={<FreshserviceProjectDetailPage />} />
            {/* Módulo de Agentes consolidado — desativado, agents-service removido do stack (2026-08-26) */}
            <Route path="/admin/agentes" element={<ModuloAgentesDesativado />} />
            <Route path="/admin/gastos" element={<ExpensesPage />} />
            <Route path="/admin/fiscal" element={<FiscalPage />} />
            <Route path="/admin/benner" element={<BennerIntegracaoPage />} />
            <Route path="/admin/benner-evolucao" element={<BennerEvolucaoPage />} />
            <Route path="/admin/governanca" element={<GovernancePage />} />
            <Route path="/admin/payfly" element={<PayFlyPage />} />
            <Route path="/admin/proposals" element={<ModuloAgentesDesativado />} />
            <Route path="/admin/cto-inbox" element={<ModuloAgentesDesativado />} />
            <Route path="/admin/orquestrador" element={<ModuloAgentesDesativado />} />
            <Route path="/admin/hermes" element={<HermesPage />} />
            <Route path="/desempenho" element={<PerformancePage />} />
            <Route path="/cartoes" element={<CartaoPage />} />
            <Route path="/financeiro" element={<FinanceiroPage />} />
            <Route path="/experiencia" element={<ExperienciaPage />} />
            <Route path="/rh" element={<RhPage />} />
            <Route path="/rh/vagas" element={<RhVagasPage />} />
            <Route path="/rh/assinatura" element={<RhAssinaturaPage />} />
            <Route path="/satisfacao" element={<SatisfacaoDashboardPage />} />
            <Route path="/satisfacao/envio" element={<SatisfacaoEnvioPage />} />
            <Route path="/satisfacao/cadastro" element={<SatisfacaoCadastroPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
    </ThemeProvider>
  );
}
