import { useState } from "react";
import { useTheme } from "../context/ThemeContext";
import DashboardTab from "../components/financeiro/DashboardTab";
import ConciliacaoTab from "../components/financeiro/ConciliacaoTab";
import ReceitasTab from "../components/financeiro/ReceitasTab";
import DespesasTab from "../components/financeiro/DespesasTab";
import BalancoTab from "../components/financeiro/BalancoTab";
import RazaoTab from "../components/financeiro/RazaoTab";
import AdiantamentosTab from "../components/financeiro/AdiantamentosTab";
import ImpostosRetidosTab from "../components/financeiro/ImpostosRetidosTab";
import LogMovimentacoesTab from "../components/financeiro/LogMovimentacoesTab";

const TABS = [
  { id: "dashboard",        label: "Dashboard" },
  { id: "conciliacao",      label: "Conciliação" },
  { id: "receitas",         label: "Receitas" },
  { id: "despesas",         label: "Despesas" },
  { id: "balanco",          label: "Balanço" },
  { id: "razao",            label: "Razão Auxiliar" },
  { id: "adiantamentos",    label: "Adiantamentos" },
  { id: "impostos",         label: "Impostos Retidos" },
  { id: "log",              label: "Log Movimentações" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function FinanceiroPage() {
  const { theme } = useTheme();
  const [tab, setTab] = useState<TabId>("dashboard");

  return (
    <div className={`min-h-screen ${theme === "dark" ? "bg-gray-950 text-gray-100" : "bg-gray-50 text-gray-900"}`}>
      <div className="max-w-screen-2xl mx-auto px-4 py-6 space-y-5">
        <div>
          <h1 className="text-2xl font-bold text-gray-800 dark:text-gray-100">Financeiro</h1>
          <p className="text-sm text-gray-500 mt-0.5">Relatórios e consultas do ERP Benner</p>
        </div>

        {/* Tab bar */}
        <div className="flex flex-wrap gap-1 border-b border-gray-200 dark:border-gray-700">
          {TABS.map(t => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`px-4 py-2 text-sm font-medium rounded-t transition-colors ${
                tab === t.id
                  ? "border-b-2 border-blue-600 text-blue-600 bg-white dark:bg-gray-900"
                  : "text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {/* Tab content */}
        <div className="bg-white dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 p-5">
          {tab === "dashboard"     && <DashboardTab />}
          {tab === "conciliacao"   && <ConciliacaoTab />}
          {tab === "receitas"      && <ReceitasTab />}
          {tab === "despesas"      && <DespesasTab />}
          {tab === "balanco"       && <BalancoTab />}
          {tab === "razao"         && <RazaoTab />}
          {tab === "adiantamentos" && <AdiantamentosTab />}
          {tab === "impostos"      && <ImpostosRetidosTab />}
          {tab === "log"           && <LogMovimentacoesTab />}
        </div>
      </div>
    </div>
  );
}
