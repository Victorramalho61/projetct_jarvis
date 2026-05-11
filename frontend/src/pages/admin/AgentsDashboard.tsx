import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useNotifications } from "../../hooks/useNotifications";
import OrchestratorPage from "./OrchestratorPage";
import CTOInboxPage from "./CTOInboxPage";
import ProposalsPage from "./ProposalsPage";
import ChangesPage from "./ChangesPage";
import AgentFlowView from "../../components/agents/AgentFlowView";
import OpportunitiesPage from "./OpportunitiesPage";

type Tab = "orquestrador" | "visualizacao" | "cto" | "proposals" | "mudancas" | "oportunidades";

const TABS: { id: Tab; label: string }[] = [
  { id: "orquestrador",  label: "Orquestrador" },
  { id: "visualizacao",  label: "Visualização ao Vivo" },
  { id: "cto",           label: "CTO" },
  { id: "proposals",     label: "Proposals" },
  { id: "mudancas",      label: "Mudanças" },
  { id: "oportunidades", label: "Oportunidades" },
];

export default function AgentsDashboard() {
  const location = useLocation();
  const navigate = useNavigate();
  const { notifications } = useNotifications();

  const getTabFromSearch = (): Tab => {
    const p = new URLSearchParams(location.search).get("tab");
    return (TABS.find(t => t.id === p)?.id ?? "orquestrador") as Tab;
  };

  const [activeTab, setActiveTab] = useState<Tab>(getTabFromSearch);

  useEffect(() => {
    setActiveTab(getTabFromSearch());
  }, [location.search]);

  const goToTab = (tab: Tab) => {
    navigate(`/admin/agentes?tab=${tab}`, { replace: true });
  };

  const ctoBadge = notifications.filter(n => n.type === "cto_message").length;
  const proposalsBadge = notifications.filter(n => n.type === "agent_proposal").length;
  const changesBadge = notifications.filter(n => n.type === "critical_event").length;

  const badge = (tab: Tab): number => {
    if (tab === "cto") return ctoBadge;
    if (tab === "proposals") return proposalsBadge;
    if (tab === "mudancas") return changesBadge;
    return 0;
  };

  const badgeStyle = (tab: Tab): string => {
    if (tab === "cto") return "bg-indigo-600 text-white animate-pulse";
    if (tab === "proposals") return "bg-orange-500 text-white";
    if (tab === "mudancas") return "bg-red-600 text-white";
    return "";
  };

  return (
    <div className="flex flex-col h-full">
      {/* Tab Bar */}
      <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 px-6 flex-shrink-0">
        <nav className="-mb-px flex gap-1" aria-label="Tabs">
          {TABS.map(tab => {
            const isActive = activeTab === tab.id;
            const count = badge(tab.id);
            return (
              <button
                key={tab.id}
                onClick={() => goToTab(tab.id)}
                className={`
                  relative flex items-center gap-1.5 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap
                  ${isActive
                    ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
                    : "border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-300"
                  }
                `}
              >
                {tab.label}
                {count > 0 && (
                  <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded-full leading-none ${badgeStyle(tab.id)}`}>
                    {count}
                  </span>
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-auto">
        {activeTab === "orquestrador"  && <OrchestratorPage />}
        {activeTab === "visualizacao"  && (
          <div className="p-6">
            <div className="mb-4">
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Visualização ao Vivo</h1>
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
                Grafo de agentes com atualização em tempo real via SSE
              </p>
            </div>
            <AgentFlowView />
          </div>
        )}
        {activeTab === "cto"           && <CTOInboxPage />}
        {activeTab === "proposals"     && <ProposalsPage />}
        {activeTab === "mudancas"      && <ChangesPage />}
        {activeTab === "oportunidades" && <OpportunitiesPage />}
      </div>
    </div>
  );
}
